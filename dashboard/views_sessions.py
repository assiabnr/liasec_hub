
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


def sessions_view(request):
    """
    Vue principale des sessions utilisateurs : durée moyenne, nombre total, clics, interactions chatbot, etc.
    Avec KPIs avancés, filtres et analytiques détaillées.
    """
    from django.db.models import F, ExpressionWrapper, fields
    from statistics import median

    # ========== FILTRES ==========
    period_filter, start_date, end_date = get_period_range(request)  # all, today, 7days, 30days, custom
    session_type_filter = request.GET.get("type", "all")  # all, with_chatbot, with_products, active, completed
    engagement_filter = request.GET.get("engagement", "all")  # all, high, medium, low, none
    min_duration = request.GET.get("min_duration", "")  # en secondes
    max_duration = request.GET.get("max_duration", "")
    search_query = request.GET.get("search", "").strip()

    today = timezone.now()

    # Base queryset
    sessions = Session.objects.prefetch_related("chatbot_interactions", "product_views")

    # Appliquer filtre période
    if period_filter in ["today", "7days", "30days"] and start_date:
        sessions = sessions.filter(start_time__gte=start_date)
    elif period_filter == "custom":
        if start_date:
            sessions = sessions.filter(start_time__gte=start_date)
        if end_date:
            sessions = sessions.filter(start_time__lte=end_date)

    # Appliquer filtre type de session
    if session_type_filter == "with_chatbot":
        sessions = sessions.filter(chatbot_interactions__isnull=False).distinct()
    elif session_type_filter == "with_products":
        sessions = sessions.filter(product_views__isnull=False).distinct()
    elif session_type_filter == "active":
        sessions = sessions.filter(end_time__isnull=True)
    elif session_type_filter == "completed":
        sessions = sessions.filter(end_time__isnull=False)

    # Appliquer filtre durée
    if min_duration:
        try:
            min_dur = int(min_duration)
            sessions = sessions.filter(duration__gte=timedelta(seconds=min_dur))
        except ValueError:
            pass

    if max_duration:
        try:
            max_dur = int(max_duration)
            sessions = sessions.filter(duration__lte=timedelta(seconds=max_dur))
        except ValueError:
            pass

    # Appliquer recherche
    if search_query:
        sessions = sessions.filter(
            Q(id__icontains=search_query) |
            Q(user_id__icontains=search_query) |
            Q(device__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    # Appliquer filtre engagement
    # On doit annoter chaque session avec son nombre total d'actions (interactions + vues produits)
    from django.db.models import Case, When, IntegerField, Value
    sessions = sessions.annotate(
        chatbot_count=Count('chatbot_interactions', distinct=True),
        products_count=Count('product_views', distinct=True)
    ).annotate(
        total_actions=F('chatbot_count') + F('products_count')
    )

    if engagement_filter == "high":
        sessions = sessions.filter(total_actions__gt=10)
    elif engagement_filter == "medium":
        sessions = sessions.filter(total_actions__gte=5, total_actions__lte=10)
    elif engagement_filter == "low":
        sessions = sessions.filter(total_actions__gte=1, total_actions__lte=4)
    elif engagement_filter == "none":
        sessions = sessions.filter(total_actions=0)

    sessions = sessions.order_by("-start_time")

    # ========== KPIs GLOBAUX ==========
    total_sessions = sessions.count()

    # Durée totale et moyenne (en soustrayant 30s de la popup d'inactivité pour avg)
    total_duration = sessions.aggregate(
        total=Coalesce(Sum("duration", output_field=DurationField()), Value(timedelta(0)))
    )["total"]
    avg_duration_raw = sessions.aggregate(avg=Avg("duration"))["avg"]

    # Soustraire 30 secondes de la durée moyenne pour la popup d'inactivité
    if avg_duration_raw:
        avg_duration_seconds = max(0, avg_duration_raw.total_seconds() - 30)
        avg_duration = timedelta(seconds=avg_duration_seconds)
    else:
        avg_duration = None

    # Durée médiane (en soustrayant 30s pour la popup d'inactivité)
    durations_list = list(sessions.filter(duration__isnull=False).values_list("duration", flat=True))
    if durations_list:
        median_duration_seconds = median([d.total_seconds() for d in durations_list])
        # Soustraire 30 secondes pour la popup d'inactivité
        median_duration_seconds = max(0, median_duration_seconds - 30)
        median_duration = timedelta(seconds=median_duration_seconds)
    else:
        median_duration = timedelta(seconds=0)

    # Sessions actives vs complétées
    active_sessions = sessions.filter(end_time__isnull=True).count()
    completed_sessions = sessions.filter(end_time__isnull=False).count()

    # Taux de rebond (sessions < 30s)
    bounce_sessions = sessions.filter(duration__lt=timedelta(seconds=30)).count()
    bounce_rate = round((bounce_sessions / total_sessions * 100), 1) if total_sessions else 0

    # Total interactions et clics (uniquement produits)
    total_chatbot_interactions = ChatbotInteraction.objects.filter(session__in=sessions).count()
    total_product_views = ProductView.objects.filter(product__isnull=False, session__in=sessions).count()

    # Sessions avec au moins une interaction chatbot
    sessions_with_chatbot = sessions.filter(chatbot_interactions__isnull=False).distinct().count()
    chatbot_session_rate = round((sessions_with_chatbot / total_sessions * 100), 1) if total_sessions else 0

    # Sessions avec au moins un produit consulté (exclure clics zones)
    sessions_with_products = sessions.filter(product_views__product__isnull=False).distinct().count()
    product_session_rate = round((sessions_with_products / total_sessions * 100), 1) if total_sessions else 0

    # Engagement moyen (interactions + vues produits par session)
    avg_engagement = round((total_chatbot_interactions + total_product_views) / total_sessions, 2) if total_sessions else 0

    # ========== STATISTIQUES D'ENGAGEMENT PAR NIVEAU ==========
    # Calculer pour TOUTES les sessions (avant filtre d'engagement)
    # On doit recalculer sur le queryset initial pour avoir les stats globales
    all_sessions_base = Session.objects.all()

    # Appliquer tous les filtres SAUF le filtre d'engagement
    if period_filter in ["today", "7days", "30days"] and start_date:
        all_sessions_base = all_sessions_base.filter(start_time__gte=start_date)
    elif period_filter == "custom":
        if start_date:
            all_sessions_base = all_sessions_base.filter(start_time__gte=start_date)
        if end_date:
            all_sessions_base = all_sessions_base.filter(start_time__lte=end_date)

    if session_type_filter == "with_chatbot":
        all_sessions_base = all_sessions_base.filter(chatbot_interactions__isnull=False).distinct()
    elif session_type_filter == "with_products":
        all_sessions_base = all_sessions_base.filter(product_views__isnull=False).distinct()
    elif session_type_filter == "active":
        all_sessions_base = all_sessions_base.filter(end_time__isnull=True)
    elif session_type_filter == "completed":
        all_sessions_base = all_sessions_base.filter(end_time__isnull=False)

    if min_duration:
        try:
            min_dur = int(min_duration)
            all_sessions_base = all_sessions_base.filter(duration__gte=timedelta(seconds=min_dur))
        except ValueError:
            pass

    if max_duration:
        try:
            max_dur = int(max_duration)
            all_sessions_base = all_sessions_base.filter(duration__lte=timedelta(seconds=max_dur))
        except ValueError:
            pass

    if search_query:
        all_sessions_base = all_sessions_base.filter(
            Q(id__icontains=search_query) |
            Q(user_id__icontains=search_query) |
            Q(device__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    all_sessions_base = all_sessions_base.annotate(
        chatbot_count=Count('chatbot_interactions', distinct=True),
        products_count=Count('product_views', distinct=True)
    ).annotate(
        total_actions=F('chatbot_count') + F('products_count')
    )

    total_sessions_base = all_sessions_base.count()
    sessions_high_engagement = all_sessions_base.filter(total_actions__gt=10).count()
    sessions_medium_engagement = all_sessions_base.filter(total_actions__gte=5, total_actions__lte=10).count()
    sessions_low_engagement = all_sessions_base.filter(total_actions__gte=1, total_actions__lte=4).count()
    sessions_no_engagement = all_sessions_base.filter(total_actions=0).count()

    # Calculer le pourcentage selon le filtre actif
    if engagement_filter == "high":
        engagement_percentage = round((sessions_high_engagement / total_sessions_base * 100), 1) if total_sessions_base else 0
        engagement_count = sessions_high_engagement
        engagement_label = "Engagement élevé"
    elif engagement_filter == "medium":
        engagement_percentage = round((sessions_medium_engagement / total_sessions_base * 100), 1) if total_sessions_base else 0
        engagement_count = sessions_medium_engagement
        engagement_label = "Engagement moyen"
    elif engagement_filter == "low":
        engagement_percentage = round((sessions_low_engagement / total_sessions_base * 100), 1) if total_sessions_base else 0
        engagement_count = sessions_low_engagement
        engagement_label = "Engagement faible"
    elif engagement_filter == "none":
        engagement_percentage = round((sessions_no_engagement / total_sessions_base * 100), 1) if total_sessions_base else 0
        engagement_count = sessions_no_engagement
        engagement_label = "Aucun engagement"
    else:  # all
        # Calculer la moyenne de tous les niveaux
        engagement_percentage = 100.0
        engagement_count = total_sessions_base
        engagement_label = "Tous niveaux"

    # Satisfaction globale (Oui / Non / Sans retour)
    all_interactions = ChatbotInteraction.objects.filter(session__in=sessions)

    # Interactions où un feedback a été demandé
    interactions_with_ask_feedback = all_interactions.filter(ask_feedback=True)
    feedbacks = interactions_with_ask_feedback.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    no_feedback = interactions_with_ask_feedback.filter(satisfaction__isnull=True).count()
    total_feedbacks = feedbacks.count()
    total_interactions_with_feedback_option = interactions_with_ask_feedback.count()

    # Taux de satisfaction incluant les conversations sans retour
    satisfaction_rate = round((satisfied / total_interactions_with_feedback_option * 100), 1) if total_interactions_with_feedback_option else 0

    # ========== COMPARAISON TEMPORELLE ==========
    # Aujourd'hui vs Hier
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    sessions_today = Session.objects.filter(start_time__gte=today_start).count()
    sessions_yesterday = Session.objects.filter(
        start_time__gte=yesterday_start,
        start_time__lt=today_start
    ).count()

    today_vs_yesterday = sessions_today - sessions_yesterday
    today_vs_yesterday_pct = round((today_vs_yesterday / sessions_yesterday * 100), 1) if sessions_yesterday else 0

    # Cette semaine vs Semaine dernière
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    last_week_start = week_start - timedelta(days=7)

    sessions_this_week = Session.objects.filter(start_time__gte=week_start).count()
    sessions_last_week = Session.objects.filter(
        start_time__gte=last_week_start,
        start_time__lt=week_start
    ).count()

    week_vs_last_week = sessions_this_week - sessions_last_week
    week_vs_last_week_pct = round((week_vs_last_week / sessions_last_week * 100), 1) if sessions_last_week else 0

    # ========== PAGINATION ==========
    paginator = Paginator(sessions, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        # Sessions paginées
        "sessions": page_obj,

        # KPIs globaux
        "total_sessions": total_sessions,
        "total_duration": format_duration(total_duration),
        "avg_duration": format_duration(avg_duration),
        "median_duration": format_duration(median_duration),
        "active_sessions": active_sessions,
        "completed_sessions": completed_sessions,
        "bounce_sessions": bounce_sessions,
        "bounce_rate": bounce_rate,

        # Engagement
        "total_chatbot_interactions": total_chatbot_interactions,
        "total_product_views": total_product_views,
        "chatbot_session_rate": chatbot_session_rate,
        "product_session_rate": product_session_rate,
        "sessions_with_chatbot": sessions_with_chatbot,
        "sessions_with_products": sessions_with_products,
        "avg_engagement": avg_engagement,

        # Statistiques d'engagement par niveau
        "sessions_high_engagement": sessions_high_engagement,
        "sessions_medium_engagement": sessions_medium_engagement,
        "sessions_low_engagement": sessions_low_engagement,
        "sessions_no_engagement": sessions_no_engagement,
        "engagement_percentage": engagement_percentage,
        "engagement_count": engagement_count,
        "engagement_label": engagement_label,

        # Satisfaction
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "no_feedback": no_feedback,
        "total_feedbacks": total_feedbacks,
        "total_interactions_with_feedback_option": total_interactions_with_feedback_option,

        # Comparaisons temporelles
        "sessions_today": sessions_today,
        "sessions_yesterday": sessions_yesterday,
        "today_vs_yesterday": today_vs_yesterday,
        "today_vs_yesterday_pct": today_vs_yesterday_pct,
        "sessions_this_week": sessions_this_week,
        "sessions_last_week": sessions_last_week,
        "week_vs_last_week": week_vs_last_week,
        "week_vs_last_week_pct": week_vs_last_week_pct,

        # Filtres actifs
        "period_filter": period_filter,
        "session_type_filter": session_type_filter,
        "engagement_filter": engagement_filter,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "search_query": search_query,
    }

    return render(request, "dashboard/sessions.html", context)

def sessions_analytics_data(request):
    """
    Fournit les données JSON pour les graphiques analytiques de la page Sessions :
    - Évolution des sessions dans le temps (30 derniers jours)
    - Distribution de la durée des sessions
    - Activité par heure de la journée
    - Répartition des devices
    - Taux d'engagement par jour
    """
    today = timezone.now()

    # ========== 1. ÉVOLUTION DES SESSIONS (30 DERNIERS JOURS) ==========
    last_30_days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    evolution_labels = []
    evolution_total = []
    evolution_with_chatbot = []
    evolution_with_products = []

    for day in last_30_days:
        evolution_labels.append(day.strftime("%d/%m"))
        day_sessions = Session.objects.filter(start_time__date=day.date())
        evolution_total.append(day_sessions.count())
        evolution_with_chatbot.append(
            day_sessions.filter(chatbot_interactions__isnull=False).distinct().count()
        )
        evolution_with_products.append(
            day_sessions.filter(product_views__isnull=False).distinct().count()
        )

    # ========== 2. DISTRIBUTION DE DURÉE ==========
    duration_ranges = [
        {"label": "0-30s", "min": 0, "max": 30},
        {"label": "30s-1m", "min": 30, "max": 60},
        {"label": "1-2m", "min": 60, "max": 120},
        {"label": "2-5m", "min": 120, "max": 300},
        {"label": "5-10m", "min": 300, "max": 600},
        {"label": "10m+", "min": 600, "max": 999999},
    ]

    duration_labels = []
    duration_counts = []

    for dr in duration_ranges:
        duration_labels.append(dr["label"])
        count = Session.objects.filter(
            duration__gte=timedelta(seconds=dr["min"]),
            duration__lt=timedelta(seconds=dr["max"])
        ).count()
        duration_counts.append(count)

    # ========== 3. ACTIVITÉ PAR HEURE (0-23h) ==========
    activity_labels = [f"{h}h" for h in range(24)]
    activity_counts = []

    for hour in range(24):
        count = Session.objects.filter(start_time__hour=hour).count()
        activity_counts.append(count)

    # ========== 4. RÉPARTITION DES DEVICES ==========
    device_stats = (
        Session.objects.exclude(device__isnull=True)
        .exclude(device="")
        .values("device")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    device_labels = [d["device"] for d in device_stats]
    device_counts = [d["count"] for d in device_stats]

    # ========== 5. TAUX D'ENGAGEMENT PAR JOUR (7 DERNIERS JOURS) ==========
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    engagement_labels = []
    engagement_rates = []

    for day in last_7_days:
        engagement_labels.append(day.strftime("%d/%m"))
        day_sessions = Session.objects.filter(start_time__date=day.date())
        total = day_sessions.count()
        engaged = day_sessions.filter(
            Q(chatbot_interactions__isnull=False) | Q(product_views__isnull=False)
        ).distinct().count()
        rate = round((engaged / total * 100), 1) if total else 0
        engagement_rates.append(rate)

    return JsonResponse({
        # Évolution
        "evolution_labels": evolution_labels,
        "evolution_total": evolution_total,
        "evolution_with_chatbot": evolution_with_chatbot,
        "evolution_with_products": evolution_with_products,

        # Distribution durée
        "duration_labels": duration_labels,
        "duration_counts": duration_counts,

        # Activité horaire
        "activity_labels": activity_labels,
        "activity_counts": activity_counts,

        # Devices
        "device_labels": device_labels,
        "device_counts": device_counts,

        # Engagement
        "engagement_labels": engagement_labels,
        "engagement_rates": engagement_rates,
    })

def session_detail_view(request, session_id):
    """
    Détail d'une session : interactions chatbot, recommandations et produits consultés.
    Avec vue conversation complète et timeline d'activité.
    Adapté selon le type de session (chatbot, produit, ou mixte).
    """
    session = get_object_or_404(Session, id=session_id)

    # ========== CONVERSATIONS CHATBOT ==========
    chats = session.chatbot_interactions.all().order_by("created_at")

    # ========== PRODUITS CONSULTÉS ==========
    # Récupérer TOUTES les vues (produits ET zones) pour la timeline
    all_views = session.product_views.select_related("product").order_by("viewed_at")
    # Mais pour les stats, uniquement les vraies consultations de produits
    products = all_views.filter(product__isnull=False)

    # ========== RECOMMANDATIONS ==========
    recommendations = session.chatbot_recommendations.select_related("product", "interaction").order_by("recommended_at")

    # ========== DÉTERMINER LE TYPE DE SESSION ==========
    has_chatbot = chats.exists()
    has_products = products.exists()

    if has_chatbot and has_products:
        session_type = "mixte"
    elif has_chatbot:
        session_type = "chatbot"
    elif has_products:
        session_type = "produit"
    else:
        session_type = "vide"

    # ========== TIMELINE COMPLÈTE (TOUS LES ÉVÉNEMENTS) ==========
    # Créer une timeline combinant interactions chatbot et TOUTES les vues (produits + zones)
    timeline = []

    # Ajouter les interactions chatbot
    for chat in chats:
        timeline.append({
            "type": "chatbot_interaction",
            "timestamp": chat.created_at,
            "data": chat
        })

    # Ajouter TOUTES les vues (produits + zones)
    for product_view in all_views:
        timeline.append({
            "type": "product_view",
            "timestamp": product_view.viewed_at,
            "data": product_view
        })

    # Trier par timestamp
    timeline.sort(key=lambda x: x["timestamp"])

    # ========== STATISTIQUES DE SESSION ==========
    # Durée de session
    duration = session.duration
    duration_formatted = None
    if duration:
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            duration_formatted = f"{hours}h {minutes}m {seconds}s"
        elif minutes:
            duration_formatted = f"{minutes}m {seconds}s"
        else:
            duration_formatted = f"{seconds}s"

    # Satisfaction (incluant les conversations sans retour)
    chats_with_ask_feedback = chats.filter(ask_feedback=True)
    feedbacks = chats_with_ask_feedback.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    total_feedbacks = feedbacks.count()
    total_with_ask_feedback = chats_with_ask_feedback.count()
    no_feedback = total_with_ask_feedback - total_feedbacks
    satisfaction_rate = round((satisfied / total_with_ask_feedback * 100), 1) if total_with_ask_feedback else None

    # Temps de réponse moyen du chatbot
    avg_response_time = chats.aggregate(avg=Avg("response_time"))["avg"]
    avg_response_time = round(avg_response_time, 2) if avg_response_time else None

    # Taux de réussite des réponses
    total_responses = chats.count()
    successful_responses = chats.filter(response_success=True).count()
    response_success_rate = round((successful_responses / total_responses * 100), 1) if total_responses else None

    # Produits uniques consultés
    unique_products = products.values("product").distinct().count()

    # Recommandations cliquées
    clicked_recos = recommendations.filter(clicked=True).count()
    total_recos = recommendations.count()
    reco_click_rate = round((clicked_recos / total_recos * 100), 1) if total_recos else None

    context = {
        "session": session,
        "duration_formatted": duration_formatted,
        "chats": chats,
        "products": all_views,  # Passer toutes les vues (produits + zones) au template
        "recommendations": recommendations,
        "timeline": timeline,

        # Type de session
        "session_type": session_type,
        "has_chatbot": has_chatbot,
        "has_products": has_products,

        # Stats satisfaction
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "no_feedback": no_feedback,
        "total_feedbacks": total_feedbacks,
        "total_with_ask_feedback": total_with_ask_feedback,

        # Stats chatbot
        "avg_response_time": avg_response_time,
        "response_success_rate": response_success_rate,
        "total_responses": total_responses,
        "successful_responses": successful_responses,

        # Stats produits
        "unique_products": unique_products,
        "total_product_views": products.count(),

        # Stats recommandations
        "clicked_recos": clicked_recos,
        "total_recos": total_recos,
        "reco_click_rate": reco_click_rate,
    }

    return render(request, "dashboard/includes/_session_detail.html", context)

@require_POST
@login_required
def delete_session_view(request, session_id):
    """Suppression d'une session (admins uniquement)."""
    user_role = getattr(request.user, 'role', None)
    if user_role != 'ADMIN':
        return JsonResponse({'success': False, 'error': 'Non autoris?'}, status=403)

    session = get_object_or_404(Session, id=session_id)
    session.soft_delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    messages.success(request, f"Session #{session_id} supprim?e.")
    return redirect('sessions')
