
import csv
import os
import re
from datetime import timedelta, datetime

from django.core.paginator import Paginator
from django.db.models import Count, Avg, Sum, DurationField, Value, Q, FloatField
from django.db.models.functions import TruncDate, Coalesce, Lower, ExtractWeekDay
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from dashboard.models import (
    Session,
    Product,
    ProductView,
    ChatbotInteraction,
    ChatbotRecommendation,
    ExportHistory,
    Settings,
    Notification,
)
from accounts.models import Role
from accounts.decorators import role_required
from liasec_hub import settings
from .view_utils import format_duration, get_period_range


def chatbot_view(request):
    """
    Vue principale du tableau de bord Chatbot :
    Analyse complète et poussée des interactions chatbot avec filtres avancés.
    """
    from statistics import median
    from collections import Counter

    # ========== FILTRES ==========
    period_filter, start_date, end_date = get_period_range(request)
    intent_filter = request.GET.get("intent", "all")
    success_filter = request.GET.get("success", "all")
    min_response_time = request.GET.get("min_response_time", "")
    max_response_time = request.GET.get("max_response_time", "")
    search_query = request.GET.get("search", "").strip()

    today = timezone.now()

    # Base queryset
    interactions = ChatbotInteraction.objects.all()

    # Appliquer filtre période
    if period_filter in ["today", "7days", "30days"] and start_date:
        interactions = interactions.filter(created_at__gte=start_date)
    elif period_filter == "custom":
        if start_date:
            interactions = interactions.filter(created_at__gte=start_date)
        if end_date:
            interactions = interactions.filter(created_at__lte=end_date)

    # Appliquer filtre intent
    if intent_filter != "all":
        interactions = interactions.filter(intent__iexact=intent_filter)

    # Appliquer filtre succès
    if success_filter == "success":
        interactions = interactions.filter(response_success=True)
    elif success_filter == "failure":
        interactions = interactions.filter(response_success=False)

    # Appliquer filtre temps de réponse
    if min_response_time:
        try:
            interactions = interactions.filter(response_time__gte=float(min_response_time))
        except ValueError:
            pass

    if max_response_time:
        try:
            interactions = interactions.filter(response_time__lte=float(max_response_time))
        except ValueError:
            pass

    # Appliquer recherche
    if search_query:
        interactions = interactions.filter(
            Q(question__icontains=search_query) | Q(response__icontains=search_query)
        )

    # ========== STATISTIQUES GLOBALES ==========
    total_interactions = interactions.count()
    total_sessions = Session.objects.count()
    sessions_with_chatbot = Session.objects.filter(chatbot_interactions__in=interactions).distinct().count()
    chatbot_session_rate = round((sessions_with_chatbot / total_sessions * 100), 1) if total_sessions else 0

    # Taux de réponse réussie et fallback
    success_count = interactions.filter(response_success=True).count()
    fallback_count = interactions.filter(response_success=False).count()
    success_rate = round((success_count / total_interactions * 100), 1) if total_interactions else 0
    fallback_rate = round((fallback_count / total_interactions * 100), 1) if total_interactions else 0

    # Temps de réponse
    response_times = list(interactions.filter(response_time__isnull=False).values_list("response_time", flat=True))
    avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0
    median_response_time = round(median(response_times), 2) if response_times else 0
    min_response_time_val = round(min(response_times), 2) if response_times else 0
    max_response_time_val = round(max(response_times), 2) if response_times else 0

    # ========== SATISFACTION (incluant conversations sans retour) ==========
    all_interactions_base = interactions
    interactions_with_ask_feedback = all_interactions_base.filter(ask_feedback=True)
    feedbacks = interactions_with_ask_feedback.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    no_feedback = interactions_with_ask_feedback.filter(satisfaction__isnull=True).count()
    total_feedbacks = feedbacks.count()
    total_with_ask_feedback = interactions_with_ask_feedback.count()
    satisfaction_rate = round((satisfied / total_with_ask_feedback * 100), 1) if total_with_ask_feedback else 0

    # ========== RECOMMANDATIONS ==========
    recommendations_qs = ChatbotRecommendation.objects.filter(interaction__in=interactions)
    total_recommendations = recommendations_qs.count()
    clicked_recos = recommendations_qs.filter(clicked=True).count()
    click_rate = round((clicked_recos / total_recommendations * 100), 1) if total_recommendations else 0

    # Taux de conversion (interactions → recommandations → clics)
    interactions_with_reco = interactions.filter(recommendations__isnull=False).distinct().count()
    reco_rate = round((interactions_with_reco / total_interactions * 100), 1) if total_interactions else 0

    # ========== COMPARAISONS TEMPORELLES ==========
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    interactions_today = ChatbotInteraction.objects.filter(created_at__gte=today_start).count()
    interactions_yesterday = ChatbotInteraction.objects.filter(
        created_at__gte=yesterday_start,
        created_at__lt=today_start
    ).count()

    today_vs_yesterday = interactions_today - interactions_yesterday
    today_vs_yesterday_pct = round((today_vs_yesterday / interactions_yesterday * 100), 1) if interactions_yesterday else 0

    # Cette semaine vs Semaine dernière
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = week_start - timedelta(days=7)

    interactions_this_week = ChatbotInteraction.objects.filter(created_at__gte=week_start).count()
    interactions_last_week = ChatbotInteraction.objects.filter(
        created_at__gte=last_week_start,
        created_at__lt=week_start
    ).count()

    week_vs_last_week = interactions_this_week - interactions_last_week
    week_vs_last_week_pct = round((week_vs_last_week / interactions_last_week * 100), 1) if interactions_last_week else 0

    # ========== TOP INTENTS ==========
    top_intents = (
        interactions
        .annotate(intent_lower=Lower("intent"))
        .values("intent_lower")
        .annotate(
            total=Count("id"),
            success_rate=Coalesce(
                Avg("response_success", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ) * 100,
            avg_response_time=Avg("response_time"),
            satisfaction_rate=Coalesce(
                Avg("satisfaction", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ) * 100,
        )
        .exclude(intent_lower__isnull=True)
        .order_by("-total")[:10]
    )

    # Pires intents (taux d'échec le plus élevé)
    worst_intents = (
        interactions
        .annotate(intent_lower=Lower("intent"))
        .values("intent_lower")
        .annotate(
            total=Count("id"),
            failure_rate=(1 - Coalesce(
                Avg("response_success", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            )) * 100,
        )
        .exclude(intent_lower__isnull=True)
        .filter(total__gte=5)  # Au moins 5 occurrences
        .order_by("-failure_rate")[:5]
    )

    # ========== QUESTIONS FRÉQUENTES ==========
    # Top 10 questions les plus posées
    questions_counter = Counter([q.lower().strip() for q in interactions.values_list("question", flat=True) if q])
    top_questions = questions_counter.most_common(10)

    # ========== TOP PRODUITS RECOMMANDÉS ==========
    top_products = (
        recommendations_qs.values("product__name", "product__id")
        .annotate(
            total=Count("id"),
            clicks=Count("id", filter=Q(clicked=True)),
            click_rate=Coalesce(
                (100.0 * Count("id", filter=Q(clicked=True)) / Count("id")),
                Value(0.0),
                output_field=FloatField()
            )
        )
        .order_by("-total")[:10]
    )

    # ========== SESSIONS LES PLUS ACTIVES ==========
    most_active_sessions = (
        interactions.values("session__id")
        .annotate(
            interaction_count=Count("id"),
            avg_response_time=Avg("response_time"),
            success_rate=Coalesce(
                Avg("response_success", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ) * 100
        )
        .order_by("-interaction_count")[:10]
    )

    # ========== ANALYSE DES ÉCHECS ==========
    failed_interactions = interactions.filter(response_success=False).order_by("-created_at")[:20]

    # Liste de tous les intents pour les filtres
    all_intents = ChatbotInteraction.objects.exclude(intent__isnull=True).values_list("intent", flat=True).distinct()

    # ========== PAGINATION DES RECOMMANDATIONS ==========
    recommendations_page_qs = (
        recommendations_qs
        .select_related("session", "interaction", "product")
        .order_by("-recommended_at")
    )
    paginator = Paginator(recommendations_page_qs, 20)
    recommendations_page = paginator.get_page(request.GET.get("page"))

    # ========== CONTEXTE ==========
    context = {
        # Interactions
        "total_interactions": total_interactions,
        "interactions_today": interactions_today,
        "interactions_yesterday": interactions_yesterday,
        "today_vs_yesterday": today_vs_yesterday,
        "today_vs_yesterday_pct": today_vs_yesterday_pct,
        "interactions_this_week": interactions_this_week,
        "interactions_last_week": interactions_last_week,
        "week_vs_last_week": week_vs_last_week,
        "week_vs_last_week_pct": week_vs_last_week_pct,

        # Performance
        "total_sessions": total_sessions,
        "sessions_with_chatbot": sessions_with_chatbot,
        "chatbot_session_rate": chatbot_session_rate,
        "success_count": success_count,
        "fallback_count": fallback_count,
        "success_rate": success_rate,
        "fallback_rate": fallback_rate,

        # Temps de réponse
        "avg_response_time": avg_response_time,
        "median_response_time": median_response_time,
        "min_response_time_val": min_response_time_val,
        "max_response_time_val": max_response_time_val,

        # Satisfaction
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "no_feedback": no_feedback,
        "total_feedbacks": total_feedbacks,

        # Recommandations
        "total_recommendations": total_recommendations,
        "clicked_recos": clicked_recos,
        "click_rate": click_rate,
        "reco_rate": reco_rate,
        "interactions_with_reco": interactions_with_reco,

        # Analyses
        "top_intents": top_intents,
        "worst_intents": worst_intents,
        "top_questions": top_questions,
        "top_products": top_products,
        "most_active_sessions": most_active_sessions,
        "failed_interactions": failed_interactions,

        # Pagination
        "recommendations": recommendations_page,

        # Filtres
        "period_filter": period_filter,
        "intent_filter": intent_filter,
        "success_filter": success_filter,
        "search_query": search_query,
        "all_intents": all_intents,
    }

    return render(request, "dashboard/chatbot.html", context)

def chatbot_analytics_data(request):
    """
    Fournit les données JSON pour les graphiques analytiques avancés du chatbot :
    - Évolution sur 30 jours (interactions, succès, temps de réponse)
    - Distribution des intents
    - Performance par modèle
    - Distribution des temps de réponse
    - Funnel d'engagement
    - Activité par heure
    """
    today = timezone.now()

    # ========== 1. ÉVOLUTION SUR 30 JOURS ==========
    last_30_days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    evolution_labels = []
    evolution_interactions = []
    evolution_success = []
    evolution_response_time = []

    for day in last_30_days:
        evolution_labels.append(day.strftime("%d/%m"))
        day_interactions = ChatbotInteraction.objects.filter(created_at__date=day.date())
        total_day = day_interactions.count()
        evolution_interactions.append(total_day)

        success_day = day_interactions.filter(response_success=True).count()
        success_rate = round((success_day / total_day * 100), 1) if total_day else 0
        evolution_success.append(success_rate)

        avg_time = day_interactions.aggregate(avg=Avg("response_time"))["avg"]
        evolution_response_time.append(round(avg_time or 0, 2))

    # ========== 2. DISTRIBUTION DES INTENTS ==========
    intent_distribution = (
        ChatbotInteraction.objects
        .exclude(intent__isnull=True)
        .annotate(intent_lower=Lower("intent"))
        .values("intent_lower")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    intent_labels = [item["intent_lower"] for item in intent_distribution]
    intent_counts = [item["count"] for item in intent_distribution]

    # ========== 3. ÉVOLUTION DE LA SATISFACTION SUR 30 JOURS ==========
    satisfaction_evolution_labels = []
    satisfaction_evolution_rates = []

    for day in last_30_days:
        satisfaction_evolution_labels.append(day.strftime("%d/%m"))
        day_interactions = ChatbotInteraction.objects.filter(created_at__date=day.date())
        # Calculate satisfaction rate (incluant conversations sans retour)
        day_with_ask_feedback = day_interactions.filter(ask_feedback=True)
        total_with_ask_feedback = day_with_ask_feedback.count()
        satisfied = day_with_ask_feedback.filter(satisfaction=True).count()
        satisfaction_rate = round((satisfied / total_with_ask_feedback * 100), 1) if total_with_ask_feedback else 0
        satisfaction_evolution_rates.append(satisfaction_rate)

    # ========== 4. TEMPS DE RÉPONSE MOYEN PAR INTENT ==========
    response_time_by_intent = (
        ChatbotInteraction.objects
        .exclude(intent__isnull=True)
        .exclude(response_time__isnull=True)
        .annotate(intent_lower=Lower("intent"))
        .values("intent_lower")
        .annotate(
            total=Count("id"),
            avg_response_time=Avg("response_time")
        )
        .filter(total__gte=5)  # Au moins 5 interactions pour être significatif
        .order_by("-avg_response_time")[:10]
    )

    response_time_intent_labels = [item["intent_lower"] for item in response_time_by_intent]
    response_time_intent_values = [round(item["avg_response_time"], 2) for item in response_time_by_intent]

    # ========== 5. DISTRIBUTION DES TEMPS DE RÉPONSE ==========
    response_time_ranges = [
        {"label": "0-0.5s", "min": 0, "max": 0.5},
        {"label": "0.5-1s", "min": 0.5, "max": 1},
        {"label": "1-2s", "min": 1, "max": 2},
        {"label": "2-3s", "min": 2, "max": 3},
        {"label": "3-5s", "min": 3, "max": 5},
        {"label": "5s+", "min": 5, "max": 999999},
    ]

    response_time_labels = []
    response_time_counts = []

    for rtr in response_time_ranges:
        response_time_labels.append(rtr["label"])
        count = ChatbotInteraction.objects.filter(
            response_time__gte=rtr["min"],
            response_time__lt=rtr["max"]
        ).count()
        response_time_counts.append(count)

    # ========== 6. FUNNEL D'ENGAGEMENT ==========
    total_interactions = ChatbotInteraction.objects.count()
    interactions_with_reco = ChatbotInteraction.objects.filter(recommendations__isnull=False).distinct().count()
    total_recos = ChatbotRecommendation.objects.count()
    clicked_recos = ChatbotRecommendation.objects.filter(clicked=True).count()

    funnel_labels = ["Interactions", "Avec recommandation", "Recommandations", "Clics"]
    funnel_values = [total_interactions, interactions_with_reco, total_recos, clicked_recos]

    # ========== 7. ACTIVITÉ PAR HEURE (0-23h) ==========
    activity_labels = [f"{h}h" for h in range(24)]
    activity_counts = []

    for hour in range(24):
        count = ChatbotInteraction.objects.filter(created_at__hour=hour).count()
        activity_counts.append(count)

    return JsonResponse({
        # Évolution
        "evolution_labels": evolution_labels,
        "evolution_interactions": evolution_interactions,
        "evolution_success": evolution_success,
        "evolution_response_time": evolution_response_time,

        # Distribution intents
        "intent_labels": intent_labels,
        "intent_counts": intent_counts,

        # Évolution de la satisfaction
        "satisfaction_evolution_labels": satisfaction_evolution_labels,
        "satisfaction_evolution_rates": satisfaction_evolution_rates,

        # Temps de réponse par intent
        "response_time_intent_labels": response_time_intent_labels,
        "response_time_intent_values": response_time_intent_values,

        # Distribution temps réponse
        "response_time_labels": response_time_labels,
        "response_time_counts": response_time_counts,

        # Funnel
        "funnel_labels": funnel_labels,
        "funnel_values": funnel_values,

        # Activité horaire
        "activity_labels": activity_labels,
        "activity_counts": activity_counts,
    })

def chatbot_question_detail(request):
    """API pour obtenir les détails d'une question spécifique"""
    question = request.GET.get("question", "").lower().strip()

    if not question:
        return JsonResponse({"error": "Question requise"}, status=400)

    interactions = ChatbotInteraction.objects.filter(question__iexact=question).order_by("-created_at")

    total = interactions.count()
    success_count = interactions.filter(response_success=True).count()
    success_rate = round((success_count / total * 100), 1) if total else 0

    # Satisfaction
    with_feedback = interactions.filter(satisfaction__isnull=False).count()
    satisfied = interactions.filter(satisfaction=True).count()
    satisfaction_rate = round((satisfied / with_feedback * 100), 1) if with_feedback else 0

    # Temps de réponse
    response_times = list(interactions.filter(response_time__isnull=False).values_list("response_time", flat=True))
    avg_time = round(sum(response_times) / len(response_times), 2) if response_times else 0

    # Intents
    intents_list = list(interactions.exclude(intent__isnull=True).values_list("intent", flat=True))

    # Dernières interactions
    recent = list(interactions[:10].values(
        "created_at", "response", "response_success", "satisfaction", "response_time", "intent"
    ))

    return JsonResponse({
        "question": question,
        "total": total,
        "success_count": success_count,
        "success_rate": success_rate,
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "with_feedback": with_feedback,
        "avg_time": avg_time,
        "intents": list(set(intents_list)),
        "recent_interactions": recent
    }, safe=False)

def chatbot_session_detail_api(request, session_id):
    """API pour obtenir les détails d'une session"""
    try:
        session = Session.objects.get(id=session_id)
    except Session.DoesNotExist:
        return JsonResponse({"error": "Session non trouvée"}, status=404)

    interactions = ChatbotInteraction.objects.filter(session=session).order_by("created_at")

    total_interactions = interactions.count()
    success_count = interactions.filter(response_success=True).count()
    success_rate = round((success_count / total_interactions * 100), 1) if total_interactions else 0

    # Satisfaction
    with_feedback = interactions.filter(satisfaction__isnull=False).count()
    satisfied = interactions.filter(satisfaction=True).count()

    # Temps de réponse
    response_times = list(interactions.filter(response_time__isnull=False).values_list("response_time", flat=True))
    avg_time = round(sum(response_times) / len(response_times), 2) if response_times else 0

    # Intents
    from collections import Counter
    intents_list = list(interactions.exclude(intent__isnull=True).values_list("intent", flat=True))
    intents_count = Counter(intents_list)

    # Toutes les interactions
    all_interactions = list(interactions.values(
        "id", "created_at", "question", "response", "response_success",
        "satisfaction", "response_time", "intent"
    ))

    return JsonResponse({
        "session_id": session_id,
        "device": session.device or "N/A",
        "start_time": session.start_time.isoformat(),
        "duration": str(session.duration) if session.duration else "N/A",
        "total_interactions": total_interactions,
        "success_count": success_count,
        "success_rate": success_rate,
        "satisfied": satisfied,
        "with_feedback": with_feedback,
        "avg_time": avg_time,
        "intents": dict(intents_count),
        "interactions": all_interactions
    }, safe=False)

def chatbot_intent_detail(request):
    """API pour obtenir les détails d'un intent spécifique"""
    intent = request.GET.get("intent", "").lower().strip()

    if not intent:
        return JsonResponse({"error": "Intent requis"}, status=400)

    interactions = ChatbotInteraction.objects.filter(intent__iexact=intent).order_by("-created_at")

    total = interactions.count()
    success_count = interactions.filter(response_success=True).count()
    failure_count = interactions.filter(response_success=False).count()
    success_rate = round((success_count / total * 100), 1) if total else 0

    # Satisfaction
    with_feedback = interactions.filter(satisfaction__isnull=False).count()
    satisfied = interactions.filter(satisfaction=True).count()
    satisfaction_rate = round((satisfied / with_feedback * 100), 1) if with_feedback else 0

    # Temps de réponse
    response_times = list(interactions.filter(response_time__isnull=False).values_list("response_time", flat=True))
    avg_time = round(sum(response_times) / len(response_times), 2) if response_times else 0

    # Questions fréquentes pour cet intent
    from collections import Counter
    questions_list = [q.lower().strip() for q in interactions.values_list("question", flat=True) if q]
    top_questions = Counter(questions_list).most_common(10)

    # Dernières interactions
    recent = list(interactions[:10].values(
        "created_at", "question", "response", "response_success", "satisfaction", "response_time"
    ))

    return JsonResponse({
        "intent": intent,
        "total": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": success_rate,
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "with_feedback": with_feedback,
        "avg_time": avg_time,
        "top_questions": [{"question": q, "count": c} for q, c in top_questions],
        "recent_interactions": recent
    }, safe=False)

def chatbot_product_detail_api(request, product_id):
    """API pour obtenir les détails d'un produit recommandé"""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Produit non trouvé"}, status=404)

    recommendations = ChatbotRecommendation.objects.filter(product=product).order_by("-recommended_at")

    total_recos = recommendations.count()
    clicked = recommendations.filter(clicked=True).count()
    click_rate = round((clicked / total_recos * 100), 1) if total_recos else 0

    # Interactions associées
    interactions = ChatbotInteraction.objects.filter(recommendations__product=product).distinct()

    # Intents associés
    from collections import Counter
    intents_list = list(interactions.exclude(intent__isnull=True).values_list("intent", flat=True))
    intents_count = Counter(intents_list).most_common(5)

    # Questions qui ont mené à ce produit
    questions_list = [q.lower().strip() for q in interactions.values_list("question", flat=True) if q]
    top_questions = Counter(questions_list).most_common(10)

    # Dernières recommandations
    recent = list(recommendations[:10].values(
        "recommended_at", "clicked", "interaction__question", "session__id"
    ))

    return JsonResponse({
        "product_id": product_id,
        "product_name": product.name,
        "product_description": product.description or "N/A",
        "total_recommendations": total_recos,
        "clicked": clicked,
        "click_rate": click_rate,
        "intents": [{"intent": i, "count": c} for i, c in intents_count],
        "top_questions": [{"question": q, "count": c} for q, c in top_questions],
        "recent_recommendations": recent
    }, safe=False)

def chatbot_interaction_detail_api(request, interaction_id):
    """API pour obtenir les détails d'une interaction en échec"""
    try:
        interaction = ChatbotInteraction.objects.select_related("session").get(id=interaction_id)
    except ChatbotInteraction.DoesNotExist:
        return JsonResponse({"error": "Interaction non trouvée"}, status=404)

    # Toutes les interactions de la session (conversation complète)
    session_interactions = ChatbotInteraction.objects.filter(
        session=interaction.session
    ).order_by("created_at")

    session_conversation = list(session_interactions.values(
        "id", "created_at", "question", "response", "response_success",
        "satisfaction", "response_time", "intent"
    ))

    # Autres interactions similaires (même question)
    similar = ChatbotInteraction.objects.filter(
        question__iexact=interaction.question
    ).exclude(id=interaction_id).order_by("-created_at")[:5]

    similar_data = list(similar.values(
        "created_at", "response_success", "satisfaction", "response_time", "intent"
    ))

    return JsonResponse({
        "id": interaction.id,
        "session_id": interaction.session.id,
        "created_at": interaction.created_at,
        "question": interaction.question,
        "response": interaction.response or "N/A",
        "intent": interaction.intent or "N/A",
        "response_success": interaction.response_success,
        "response_time": interaction.response_time,
        "satisfaction": interaction.satisfaction,
        "session_conversation": session_conversation,
        "similar_interactions": similar_data
    }, safe=False)

def chatbot_chart_data(request):
    """
    Fournit les données JSON pour les graphiques du tableau de bord Chatbot :
    - Évolution du nombre d’interactions par jour
    - Temps moyen de réponse
    - Top produits recommandés
    """
    today = timezone.now()
    start_date = today - timedelta(days=6)

    # Récupération des interactions des 7 derniers jours
    date_labels = []
    interactions_per_day = []
    avg_response_times = []

    for i in range(7):
        day = start_date + timedelta(days=i)
        date_str = day.strftime("%d/%m")
        date_labels.append(date_str)

        # Nombre d'interactions ce jour-là
        day_interactions = ChatbotInteraction.objects.filter(created_at__date=day.date())
        interactions_per_day.append(day_interactions.count())

        # Temps de réponse moyen du jour
        avg_time = day_interactions.aggregate(avg=Avg("response_time"))["avg"] or 0
        avg_response_times.append(round(avg_time, 2))

    # Top 5 produits les plus recommandés
    top_products_qs = (
        ChatbotRecommendation.objects.values("product__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    top_products = {
        "labels": [p["product__name"] for p in top_products_qs],
        "values": [p["total"] for p in top_products_qs],
    }

    # Résumé global JSON
    data = {
        "labels": date_labels,
        "interactions": interactions_per_day,
        "avg_response_times": avg_response_times,
        "top_products": top_products,
    }

    return JsonResponse(data)
