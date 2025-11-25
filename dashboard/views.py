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
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from dashboard.models import (
    Session,
    Click,
    Product,
    ProductView,
    ChatbotInteraction,
    ChatbotRecommendation,
    ExportHistory,
    Settings,
)
from accounts.models import Role
from accounts.decorators import role_required
from liasec_hub import settings


# ==========================
# VUE D’ACCUEIL DU DASHBOARD
# ==========================
def dashboard_home(request):
    import json
    from django.db.models.functions import TruncDate
    from django.db.models import Avg, Sum, F, Q, FloatField
    from django.db.models.functions import Cast

    # ========== PÉRIODE DE COMPARAISON ==========
    today = timezone.now()
    last_7_days = today - timedelta(days=7)
    previous_7_days = last_7_days - timedelta(days=7)

    # ========== SESSIONS ==========
    sessions_total = Session.objects.count()
    sessions_last_7 = Session.objects.filter(start_time__gte=last_7_days).count()
    sessions_previous_7 = Session.objects.filter(
        start_time__gte=previous_7_days, start_time__lt=last_7_days
    ).count()

    sessions_variation = 0
    if sessions_previous_7 > 0:
        sessions_variation = round(((sessions_last_7 - sessions_previous_7) / sessions_previous_7) * 100, 1)

    # Durée moyenne des sessions (en soustrayant 30s pour la popup d'inactivité)
    avg_duration = Session.objects.filter(
        duration__isnull=False
    ).aggregate(avg_duration=Avg("duration"))["avg_duration"]

    if avg_duration:
        # Soustraire 30 secondes (durée de la popup d'inactivité)
        avg_duration_seconds = avg_duration.total_seconds() - 30
        # S'assurer que la durée reste positive
        avg_duration_seconds = max(0, avg_duration_seconds)
        avg_duration_minutes = round(avg_duration_seconds / 60, 1)
    else:
        avg_duration_minutes = 0

    # Sessions actives (avec au moins une interaction)
    active_sessions = Session.objects.filter(
        Q(chatbot_interactions__isnull=False) | Q(product_views__isnull=False)
    ).distinct().count()
    active_sessions_rate = round((active_sessions / sessions_total * 100), 1) if sessions_total > 0 else 0

    # ========== CHATBOT ==========
    interactions_total = ChatbotInteraction.objects.count()
    interactions_last_7 = ChatbotInteraction.objects.filter(created_at__gte=last_7_days).count()
    interactions_previous_7 = ChatbotInteraction.objects.filter(
        created_at__gte=previous_7_days, created_at__lt=last_7_days
    ).count()

    interactions_variation = 0
    if interactions_previous_7 > 0:
        interactions_variation = round(((interactions_last_7 - interactions_previous_7) / interactions_previous_7) * 100, 1)

    # Taux de satisfaction (incluant les conversations sans retour)
    # On compte toutes les interactions où un feedback a été demandé
    satisfaction_data = ChatbotInteraction.objects.filter(
        ask_feedback=True
    ).aggregate(
        positive=Count("id", filter=Q(satisfaction=True)),
        total=Count("id")
    )
    satisfaction_rate = round((satisfaction_data["positive"] / satisfaction_data["total"] * 100), 1) if satisfaction_data["total"] > 0 else 0

    # Taux de succès
    success_data = ChatbotInteraction.objects.aggregate(
        success=Count("id", filter=Q(response_success=True)),
        total=Count("id")
    )
    success_rate = round((success_data["success"] / success_data["total"] * 100), 1) if success_data["total"] > 0 else 0

    # Temps de réponse moyen
    avg_response_time = ChatbotInteraction.objects.filter(
        response_time__isnull=False
    ).aggregate(avg_time=Avg("response_time"))["avg_time"]
    avg_response_time = round(avg_response_time, 2) if avg_response_time else 0

    # ========== PRODUITS ==========
    products_total = Product.objects.filter(available=True).count()
    product_views_total = ProductView.objects.count()
    product_views_last_7 = ProductView.objects.filter(viewed_at__gte=last_7_days).count()
    product_views_previous_7 = ProductView.objects.filter(
        viewed_at__gte=previous_7_days, viewed_at__lt=last_7_days
    ).count()

    product_views_variation = 0
    if product_views_previous_7 > 0:
        product_views_variation = round(((product_views_last_7 - product_views_previous_7) / product_views_previous_7) * 100, 1)

    # Produit le plus consulté
    top_product = ProductView.objects.filter(
        product__isnull=False
    ).values(
        "product__name"
    ).annotate(
        count=Count("id")
    ).order_by("-count").first()

    # Vues par produit unique
    unique_products_viewed = ProductView.objects.filter(
        product__isnull=False
    ).values("product").distinct().count()
    avg_views_per_product = round(product_views_total / unique_products_viewed, 1) if unique_products_viewed > 0 else 0

    # ========== CLICS ==========
    clicks_total = Click.objects.count()
    clicks_last_7 = Click.objects.filter(timestamp__gte=last_7_days).count()
    clicks_previous_7 = Click.objects.filter(
        timestamp__gte=previous_7_days, timestamp__lt=last_7_days
    ).count()

    clicks_variation = 0
    if clicks_previous_7 > 0:
        clicks_variation = round(((clicks_last_7 - clicks_previous_7) / clicks_previous_7) * 100, 1)

    # ========== RECOMMANDATIONS CHATBOT ==========
    recommendations_total = ChatbotRecommendation.objects.count()
    recommendations_clicked = ChatbotRecommendation.objects.filter(clicked=True).count()
    recommendations_ctr = round((recommendations_clicked / recommendations_total * 100), 1) if recommendations_total > 0 else 0

    # ========== TOP INTENTS ==========
    top_intents = ChatbotInteraction.objects.filter(
        intent__isnull=False
    ).exclude(
        intent=""
    ).values("intent").annotate(
        count=Count("id")
    ).order_by("-count")[:5]

    # ========== TOP PRODUITS ==========
    top_products = ProductView.objects.filter(
        product__isnull=False
    ).values(
        "product__name", "product__id"
    ).annotate(
        views=Count("id")
    ).order_by("-views")[:5]

    # ========== SOURCES DE CONSULTATION ==========
    sources_data = ProductView.objects.exclude(
        source="localisation"
    ).values("source").annotate(
        count=Count("id")
    ).order_by("-count")

    # ========== ÉVOLUTION 7 DERNIERS JOURS ==========
    evolution_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_data = {
            "date": day.strftime("%d/%m"),
            "sessions": Session.objects.filter(start_time__date=day.date()).count(),
            "interactions": ChatbotInteraction.objects.filter(created_at__date=day.date()).count(),
            "product_views": ProductView.objects.filter(viewed_at__date=day.date()).count(),
            "clicks": Click.objects.filter(timestamp__date=day.date()).count(),
        }
        evolution_data.append(day_data)

    context = {
        # Sessions
        "sessions_total": sessions_total,
        "sessions_last_7": sessions_last_7,
        "sessions_variation": sessions_variation,
        "avg_duration_minutes": avg_duration_minutes,
        "active_sessions": active_sessions,
        "active_sessions_rate": active_sessions_rate,

        # Chatbot
        "interactions_total": interactions_total,
        "interactions_last_7": interactions_last_7,
        "interactions_variation": interactions_variation,
        "satisfaction_rate": satisfaction_rate,
        "success_rate": success_rate,
        "avg_response_time": avg_response_time,

        # Produits
        "products_total": products_total,
        "product_views_total": product_views_total,
        "product_views_last_7": product_views_last_7,
        "product_views_variation": product_views_variation,
        "top_product": top_product,
        "unique_products_viewed": unique_products_viewed,
        "avg_views_per_product": avg_views_per_product,

        # Clics
        "clicks_total": clicks_total,
        "clicks_last_7": clicks_last_7,
        "clicks_variation": clicks_variation,

        # Recommandations
        "recommendations_total": recommendations_total,
        "recommendations_clicked": recommendations_clicked,
        "recommendations_ctr": recommendations_ctr,

        # Top données
        "top_intents": top_intents,
        "top_products": top_products,
        "sources_data": sources_data,

        # Évolution
        "evolution_data": json.dumps(evolution_data),
    }
    return render(request, "dashboard/dashboard_home.html", context)


# ==========================
# DONNÉES GRAPHIQUE PRINCIPAL
# ==========================
def chart_data(request):
    labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

    # Sessions : moyenne par jour de semaine
    sessions_qs = (
        Session.objects
        .annotate(day=ExtractWeekDay("start_time"))
        .values("day")
        .annotate(avg_sessions=Count("id") * 1.0 / Count("start_time__week", distinct=True))
        .order_by("day")
    )

    # Clics : moyenne par jour de semaine
    clicks_qs = (
        Click.objects
        .annotate(day=ExtractWeekDay("timestamp"))
        .values("day")
        .annotate(avg_clicks=Count("id") * 1.0 / Count("timestamp__week", distinct=True))
        .order_by("day")
    )

    # Mapping Django weekday (1=Dimanche → 7=Samedi)
    mapping = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    sessions_data = [0] * 7
    clicks_data = [0] * 7

    for s in sessions_qs:
        index = mapping.get(s["day"], None)
        if index is not None:
            sessions_data[index] = round(s["avg_sessions"], 2)

    for c in clicks_qs:
        index = mapping.get(c["day"], None)
        if index is not None:
            clicks_data[index] = round(c["avg_clicks"], 2)

    return JsonResponse({
        "labels": labels,
        "sessions": sessions_data,
        "clicks": clicks_data
    })

# ==========================
# SESSIONS
# ==========================
def sessions_view(request):
    """
    Vue principale des sessions utilisateurs : durée moyenne, nombre total, clics, interactions chatbot, etc.
    Avec KPIs avancés, filtres et analytiques détaillées.
    """
    from django.db.models import F, ExpressionWrapper, fields
    from statistics import median

    # ========== FILTRES ==========
    period_filter = request.GET.get("period", "all")  # all, today, 7days, 30days, custom
    session_type_filter = request.GET.get("type", "all")  # all, with_chatbot, with_products, active, completed
    engagement_filter = request.GET.get("engagement", "all")  # all, high, medium, low, none
    min_duration = request.GET.get("min_duration", "")  # en secondes
    max_duration = request.GET.get("max_duration", "")
    search_query = request.GET.get("search", "").strip()

    # Date de début selon le filtre période
    today = timezone.now()
    if period_filter == "today":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_filter == "7days":
        start_date = today - timedelta(days=7)
    elif period_filter == "30days":
        start_date = today - timedelta(days=30)
    elif period_filter == "custom":
        custom_start = request.GET.get("start_date")
        custom_end = request.GET.get("end_date")
        start_date = timezone.datetime.strptime(custom_start, "%Y-%m-%d") if custom_start else None
        end_date = timezone.datetime.strptime(custom_end, "%Y-%m-%d") if custom_end else None
    else:
        start_date = None
        end_date = None

    # Base queryset
    sessions = Session.objects.prefetch_related("clicks", "chatbot_interactions", "product_views")

    # Appliquer filtre période
    if period_filter in ["today", "7days", "30days"] and start_date:
        sessions = sessions.filter(start_time__gte=start_date)
    elif period_filter == "custom" and start_date and end_date:
        sessions = sessions.filter(start_time__gte=start_date, start_time__lte=end_date)

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

    # Total interactions et clics
    total_chatbot_interactions = ChatbotInteraction.objects.filter(session__in=sessions).count()
    total_product_views = ProductView.objects.filter(session__in=sessions).count()

    # Sessions avec au moins une interaction chatbot
    sessions_with_chatbot = sessions.filter(chatbot_interactions__isnull=False).distinct().count()
    chatbot_session_rate = round((sessions_with_chatbot / total_sessions * 100), 1) if total_sessions else 0

    # Sessions avec au moins un produit consulté
    sessions_with_products = sessions.filter(product_views__isnull=False).distinct().count()
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
    elif period_filter == "custom" and start_date and end_date:
        all_sessions_base = all_sessions_base.filter(start_time__gte=start_date, start_time__lte=end_date)

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

    # Formatage des durées
    def format_duration(td):
        if not td:
            return "—"
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

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
    products = session.product_views.select_related("product").order_by("viewed_at")

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
    # Créer une timeline combinant interactions chatbot et vues produits
    timeline = []

    # Ajouter les interactions chatbot
    for chat in chats:
        timeline.append({
            "type": "chatbot_interaction",
            "timestamp": chat.created_at,
            "data": chat
        })

    # Ajouter les vues produits
    for product_view in products:
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
        "products": products,
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
        "total_feedbacks": total_feedbacks,

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


# ==========================
# CLICS
# ==========================
def clicks_view(request):
    """
    Vue complète des consultations produits avec statistiques par source.
    Utilise ProductView pour tracker tous les clics (chatbot, carte, recherche).
    """
    # Récupérer toutes les consultations de produits
    product_views = ProductView.objects.select_related("session", "product").order_by("-viewed_at")

    # Filtrage par source si demandé
    source_filter = request.GET.get("source")
    if source_filter and source_filter in ["chatbot", "carte", "recherche"]:
        product_views = product_views.filter(source=source_filter)

    # Statistiques globales
    total_clicks = ProductView.objects.count()
    clicks_chatbot = ProductView.objects.filter(source="chatbot").count()
    clicks_carte = ProductView.objects.filter(source="carte").count()
    clicks_recherche = ProductView.objects.filter(source="recherche").count()

    # Calcul des pourcentages
    pct_chatbot = round((clicks_chatbot / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_carte = round((clicks_carte / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_recherche = round((clicks_recherche / total_clicks * 100), 1) if total_clicks > 0 else 0

    # Taux de conversion des recommandations chatbot
    from dashboard.models import ChatbotRecommendation
    total_recommendations = ChatbotRecommendation.objects.count()
    clicked_recommendations = ChatbotRecommendation.objects.filter(clicked=True).count()
    conversion_rate = round((clicked_recommendations / total_recommendations * 100), 1) if total_recommendations > 0 else 0

    # Pagination
    paginator = Paginator(product_views, 20)

    context = {
        "clicks": paginator.get_page(request.GET.get("page")),
        "total_clicks": total_clicks,
        "clicks_chatbot": clicks_chatbot,
        "clicks_carte": clicks_carte,
        "clicks_recherche": clicks_recherche,
        "pct_chatbot": pct_chatbot,
        "pct_carte": pct_carte,
        "pct_recherche": pct_recherche,
        "source_filter": source_filter,
        "total_recommendations": total_recommendations,
        "clicked_recommendations": clicked_recommendations,
        "conversion_rate": conversion_rate,
    }

    return render(request, "dashboard/clicks.html", context)


def clicks_chart_data(request):
    """
    Données pour les graphiques de la page Clics.
    - Clics par jour (7 derniers jours)
    - Produits les plus consultés (top 5)
    - Répartition par source (chatbot, carte, recherche)
    """
    today = timezone.now()
    start_date = today - timedelta(days=6)

    # 1. Consultations par jour
    clicks_per_day = (
        ProductView.objects.filter(viewed_at__date__gte=start_date.date())
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    labels = [c["day"].strftime("%d/%m") for c in clicks_per_day]
    values = [c["total"] for c in clicks_per_day]

    # 2. Top 5 produits les plus consultés
    top_products = (
        ProductView.objects.values("product__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # 3. Répartition par source
    clicks_by_source = {
        "chatbot": ProductView.objects.filter(source="chatbot").count(),
        "carte": ProductView.objects.filter(source="carte").count(),
        "recherche": ProductView.objects.filter(source="recherche").count(),
    }

    return JsonResponse({
        "labels": labels,
        "clicks_per_day": values,
        "labels_types": [p["product__name"] for p in top_products],
        "clicks_by_label": [p["total"] for p in top_products],
        "clicks_by_source": clicks_by_source,
    })


# ==========================
# PRODUITS
# ==========================
def produits_view(request):
    """
    Tableau de bord Produits - Version complète
    Analyse visibilité, performance, disponibilité et tendances des produits.
    """
    # ========== FILTRES ET RECHERCHE ==========
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    availability_filter = request.GET.get('availability', '')
    sort_by = request.GET.get('sort', '-total_views')  # Par défaut: plus consultés

    # ========== INDICATEURS GLOBAUX ==========
    total_products = Product.objects.count()
    available_products = Product.objects.filter(available=True).count()
    unavailable_products = Product.objects.filter(available=False).count()

    total_views = ProductView.objects.count()
    total_recos = ChatbotRecommendation.objects.count()
    total_clicks = ProductView.objects.exclude(source__isnull=True).count()

    # Vues uniques (par produit)
    unique_viewed_products = ProductView.objects.values('product').distinct().count()

    # Pourcentages
    pct_available = round((available_products / total_products * 100), 1) if total_products > 0 else 0
    pct_unavailable = round((unavailable_products / total_products * 100), 1) if total_products > 0 else 0
    pct_viewed = round((unique_viewed_products / total_products * 100), 1) if total_products > 0 else 0

    # Taux moyen de clics sur produit
    avg_click_rate = round((total_clicks / total_views * 100), 2) if total_views else 0

    # Prix moyen des produits consultés
    avg_viewed_price = (
        Product.objects.filter(views__isnull=False)
        .aggregate(avg=Coalesce(Avg("price", output_field=FloatField()), Value(0.0)))["avg"]
    )

    # Taux de conversion "recommandation → clic"
    clicked_recos = ChatbotRecommendation.objects.filter(clicked=True).count()
    conversion_rate = round((clicked_recos / total_recos * 100), 2) if total_recos else 0

    # ========== PERFORMANCE PRODUITS ==========

    # Top 10 produits les plus consultés
    top_viewed = (
        ProductView.objects
        .filter(product__isnull=False)
        .values("product__name", "product__id")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    # Top 10 produits les plus recommandés
    top_recommended = (
        ChatbotRecommendation.objects.values("product__name", "product__id")
        .annotate(recos=Count("id"))
        .order_by("-recos")[:10]
    )

    # Taux de clics (clics / recommandations)
    top_click_rate = (
        ChatbotRecommendation.objects
        .values("product__name", "product__id")
        .annotate(
            recos=Count("id"),
            clicks=Count("id", filter=Q(clicked=True)),
            click_rate=Coalesce(
                (100.0 * Count("id", filter=Q(clicked=True)) / Count("id")),
                Value(0.0),
                output_field=FloatField()
            ),
        )
        .order_by("-click_rate")[:10]
    )

    # Évolution des vues produits (7 derniers jours)
    today = timezone.now()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    view_labels, view_counts = [], []
    for day in last_7_days:
        view_labels.append(day.strftime("%d/%m"))
        view_counts.append(
            ProductView.objects.filter(viewed_at__date=day.date()).count()
        )

    # ========== DISPONIBILITÉ / ANOMALIES ==========

    # Produits populaires mais indisponibles
    popular_unavailable = (
        ProductView.objects
        .filter(product__available=False)
        .values("product__name", "product__id")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    # Produits jamais consultés
    never_viewed = Product.objects.filter(views__isnull=True)[:10]

    # Produits avec informations manquantes
    incomplete_products = Product.objects.filter(
        Q(price__isnull=True) |
        Q(image_url__isnull=True) |
        Q(category__isnull=True) |
        Q(name__exact="")
    )[:10]

    # Évolution du taux de disponibilité (7 derniers jours)
    availability_labels, availability_data = [], []
    for day in last_7_days:
        availability_labels.append(day.strftime("%d/%m"))
        available = Product.objects.filter(available=True).count()
        availability_data.append(round((available / total_products * 100), 2) if total_products else 0)

    # ========== ANALYSES CROISÉES ==========

    # Corrélation produits recommandés ↔ cliqués
    correlation_data = (
        ChatbotRecommendation.objects
        .values("product__name")
        .annotate(
            recos=Count("id"),
            clicks=Count("id", filter=Q(clicked=True)),
        )
        .order_by("-recos")[:15]
    )

    # Produits les plus mentionnés dans les conversations chatbot
    mentioned_products = (
        ChatbotRecommendation.objects
        .values("product__name")
        .annotate(total_mentions=Count("interaction__id"))
        .order_by("-total_mentions")[:10]
    )

    # Catégories les plus performantes via chatbot
    top_categories = (
        Product.objects.values("category")
        .annotate(
            recos=Count("chatbot_recommendations"),
            clicks=Count("views"),
        )
        .order_by("-clicks")[:10]
    )

    # ========== EXPLORATION / PAGINATION ==========
    all_products = (
        Product.objects
        .annotate(
            total_views=Count("views"),
            total_recos=Count("chatbot_recommendations"),
            clicked_recos=Count("chatbot_recommendations", filter=Q(chatbot_recommendations__clicked=True)),
            click_rate=Coalesce(
                (100.0 * Count("chatbot_recommendations", filter=Q(chatbot_recommendations__clicked=True)) /
                 Count("chatbot_recommendations")),
                Value(0.0),
                output_field=FloatField()
            ),
        )
    )

    # Appliquer les filtres
    if search_query:
        all_products = all_products.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(product_id__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    if category_filter:
        all_products = all_products.filter(category=category_filter)

    if availability_filter == 'available':
        all_products = all_products.filter(available=True)
    elif availability_filter == 'unavailable':
        all_products = all_products.filter(available=False)

    # Appliquer le tri
    valid_sorts = ['name', '-name', 'price', '-price', 'total_views', '-total_views',
                   'total_recos', '-total_recos', 'click_rate', '-click_rate']
    if sort_by in valid_sorts:
        all_products = all_products.order_by(sort_by)
    else:
        all_products = all_products.order_by('-total_views')

    # Récupérer toutes les catégories disponibles
    all_categories = Product.objects.values_list('category', flat=True).distinct().exclude(category__isnull=True).exclude(category='').order_by('category')

    paginator = Paginator(all_products, 20)
    products_page = paginator.get_page(request.GET.get("page"))
    recos_dict = {r["product__name"]: r["recos"] for r in top_recommended}

    # ========== CONTEXTE ==========
    context = {
        # KPIs globaux
        "total_products": total_products,
        "available_products": available_products,
        "unavailable_products": unavailable_products,
        "pct_available": pct_available,
        "pct_unavailable": pct_unavailable,
        "pct_viewed": pct_viewed,
        "total_views": total_views,
        "total_recos": total_recos,
        "unique_viewed_products": unique_viewed_products,
        "avg_click_rate": avg_click_rate,
        "avg_viewed_price": avg_viewed_price,
        "conversion_rate": conversion_rate,
        "recos_dict": recos_dict,

        # Performances
        "top_viewed": top_viewed,
        "top_recommended": top_recommended,
        "top_click_rate": top_click_rate,
        "view_labels": view_labels,
        "view_counts": view_counts,

        # Disponibilité
        "popular_unavailable": popular_unavailable,
        "never_viewed": never_viewed,
        "incomplete_products": incomplete_products,
        "availability_labels": availability_labels,
        "availability_data": availability_data,

        # Analyses croisées
        "correlation_data": correlation_data,
        "mentioned_products": mentioned_products,
        "top_categories": top_categories,

        # Liste produits
        "products": products_page,

        # Filtres
        "search_query": search_query,
        "category_filter": category_filter,
        "availability_filter": availability_filter,
        "sort_by": sort_by,
        "all_categories": all_categories,
    }

    return render(request, "dashboard/produits.html", context)



def product_detail_view(request, product_id):
    """
    Vue détaillée d'un produit spécifique avec toutes ses métriques.
    """
    product = get_object_or_404(Product, id=product_id)

    # Statistiques générales
    total_views = product.views.count()
    total_recos = product.chatbot_recommendations.count()
    clicked_recos = product.chatbot_recommendations.filter(clicked=True).count()
    conversion_rate = round((clicked_recos / total_recos * 100), 1) if total_recos > 0 else 0

    # Vues par source
    views_by_source = (
        product.views.values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Évolution des vues (7 derniers jours)
    today = timezone.now()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    view_dates = []
    view_counts = []
    for day in last_7_days:
        view_dates.append(day.strftime("%d/%m"))
        view_counts.append(product.views.filter(viewed_at__date=day.date()).count())

    # Sessions ayant consulté ce produit
    recent_views = product.views.select_related('session').order_by('-viewed_at')[:20]

    # Recommandations liées
    recent_recos = product.chatbot_recommendations.select_related('session', 'interaction').order_by('-recommended_at')[:20]

    # Produits similaires (même catégorie, consultés)
    similar_products = (
        Product.objects
        .filter(category=product.category)
        .exclude(id=product.id)
        .annotate(views_count=Count('views'))
        .filter(views_count__gt=0)
        .order_by('-views_count')[:10]
    )

    context = {
        'product': product,
        'total_views': total_views,
        'total_recos': total_recos,
        'clicked_recos': clicked_recos,
        'conversion_rate': conversion_rate,
        'views_by_source': views_by_source,
        'view_dates': view_dates,
        'view_counts': view_counts,
        'recent_views': recent_views,
        'recent_recos': recent_recos,
        'similar_products': similar_products,
    }

    return render(request, "dashboard/product_detail.html", context)


def products_chart_data(request):
    """
    Données JSON complètes pour les graphiques produits
    """
    # Top 10 produits les plus consultés
    top_views = (
        ProductView.objects.values("product__name", "product__id")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    # Top 10 recommandations
    top_recos = (
        ChatbotRecommendation.objects.values("product__name", "product__id")
        .annotate(recos=Count("id"))
        .order_by("-recos")[:10]
    )

    # Vues par catégorie
    views_by_category = (
        ProductView.objects.values("product__category")
        .exclude(product__category__isnull=True)
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )

    # Distribution des prix des produits consultés
    price_ranges = [
        {"range": "0-50€", "min": 0, "max": 50},
        {"range": "50-100€", "min": 50, "max": 100},
        {"range": "100-200€", "min": 100, "max": 200},
        {"range": "200-500€", "min": 200, "max": 500},
        {"range": "500€+", "min": 500, "max": 999999},
    ]
    price_distribution = []
    for pr in price_ranges:
        count = ProductView.objects.filter(
            product__price__gte=pr["min"],
            product__price__lt=pr["max"]
        ).count()
        price_distribution.append(count)

    # Évolution vues produits (7 derniers jours)
    today = timezone.now()
    views_7days_labels = []
    views_7days_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        views_7days_labels.append(day.strftime("%d/%m"))
        count = ProductView.objects.filter(viewed_at__date=day.date()).count()
        views_7days_data.append(count)

    # Sources de consultation des produits (en excluant "localisation")
    sources_distribution = (
        ProductView.objects.exclude(source="localisation")
        .values("source")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Préparer les données des sources
    sources_labels = []
    sources_data = []
    sources_colors = []

    source_mapping = {
        "chatbot": {"label": "Chatbot", "color": "#3B82F6"},
        "carte": {"label": "Carte Interactive", "color": "#10B981"},
        "recherche": {"label": "Recherche", "color": "#F59E0B"},
    }

    for source in sources_distribution:
        source_key = source["source"] or "autre"
        mapping = source_mapping.get(source_key, {"label": source_key.capitalize(), "color": "#6B7280"})
        sources_labels.append(mapping["label"])
        sources_data.append(source["count"])
        sources_colors.append(mapping["color"])

    return JsonResponse({
        # Sources de consultation
        "sources_labels": sources_labels,
        "sources_data": sources_data,
        "sources_colors": sources_colors,

        # Catégories
        "categories_labels": [c["product__category"] for c in views_by_category],
        "categories_data": [c["count"] for c in views_by_category],

        # Prix
        "price_labels": [pr["range"] for pr in price_ranges],
        "price_data": price_distribution,

        # Évolution
        "views_7days_labels": views_7days_labels,
        "views_7days_data": views_7days_data,
    })



# ==========================
# CHATBOT
# ==========================


def chatbot_view(request):
    """
    Vue principale du tableau de bord Chatbot :
    Analyse complète et poussée des interactions chatbot avec filtres avancés.
    """
    from statistics import median
    from collections import Counter

    # ========== FILTRES ==========
    period_filter = request.GET.get("period", "all")
    intent_filter = request.GET.get("intent", "all")
    success_filter = request.GET.get("success", "all")
    min_response_time = request.GET.get("min_response_time", "")
    max_response_time = request.GET.get("max_response_time", "")
    search_query = request.GET.get("search", "").strip()

    # Date de début selon le filtre période
    today = timezone.now()
    if period_filter == "today":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_filter == "7days":
        start_date = today - timedelta(days=7)
    elif period_filter == "30days":
        start_date = today - timedelta(days=30)
    elif period_filter == "custom":
        custom_start = request.GET.get("start_date")
        custom_end = request.GET.get("end_date")
        start_date = timezone.datetime.strptime(custom_start, "%Y-%m-%d") if custom_start else None
        end_date = timezone.datetime.strptime(custom_end, "%Y-%m-%d") if custom_end else None
    else:
        start_date = None
        end_date = None

    # Base queryset
    interactions = ChatbotInteraction.objects.all()

    # Appliquer filtre période
    if period_filter in ["today", "7days", "30days"] and start_date:
        interactions = interactions.filter(created_at__gte=start_date)
    elif period_filter == "custom" and start_date and end_date:
        interactions = interactions.filter(created_at__gte=start_date, created_at__lte=end_date)

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
        "user_agent": session.user_agent or "N/A",
        "created_at": session.created_at,
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

# ==========================
# PARAMÈTRES ET EXPORTS
# ==========================
def settings_view(request):
    settings_obj, _ = Settings.objects.get_or_create(id=1)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save":
            settings_obj.name = request.POST.get("name", settings_obj.name)
            settings_obj.location = request.POST.get("location", settings_obj.location)
            settings_obj.code = request.POST.get("code", settings_obj.code)
            settings_obj.track_sessions = request.POST.get("track_sessions") == "on"
            settings_obj.track_clicks = request.POST.get("track_clicks") == "on"
            settings_obj.track_chatbot = request.POST.get("track_chatbot") == "on"
            settings_obj.save()
            messages.success(request, "Paramètres sauvegardés avec succès.")
            return redirect("settings")

        elif action == "reset":
            Session.objects.all().delete()
            Click.objects.all().delete()
            ChatbotInteraction.objects.all().delete()
            ProductView.objects.all().delete()
            ChatbotRecommendation.objects.all().delete()
            messages.warning(request, "Toutes les données ont été réinitialisées.")
            return redirect("settings")

    return render(request, "dashboard/settings.html", {"settings": settings_obj})


@csrf_exempt
def reset_data_view(request):
    if request.method == "POST":
        Session.objects.all().delete()
        Click.objects.all().delete()
        ChatbotInteraction.objects.all().delete()
        ProductView.objects.all().delete()
        ChatbotRecommendation.objects.all().delete()
        ExportHistory.objects.all().delete()
        return JsonResponse({"success": True, "message": "Toutes les données ont été réinitialisées."})
    return JsonResponse({"success": False, "error": "Méthode non autorisée."}, status=405)


def export_history_view(request):
    settings_obj = Settings.objects.first()
    if not settings_obj:
        return HttpResponse("Aucune configuration trouvée.", content_type="text/plain")

    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="configuration_liasec.csv"'

    writer = csv.writer(response)
    writer.writerow(["Nom de la borne", "Localisation", "Code", "Suivi sessions", "Suivi clics", "Suivi chatbot", "Dernière mise à jour"])
    writer.writerow([
        settings_obj.name,
        settings_obj.location,
        settings_obj.code,
        "Oui" if settings_obj.track_sessions else "Non",
        "Oui" if settings_obj.track_clicks else "Non",
        "Oui" if settings_obj.track_chatbot else "Non",
        settings_obj.updated_at.strftime("%d/%m/%Y %H:%M")
    ])
    return response


def exports_view(request):
    exports = ExportHistory.objects.all().order_by('-exported_at')[:10]
    return render(request, "dashboard/exports.html", {"exports": exports})


@csrf_exempt
def export_data_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    data_type = request.POST.get("data_type")
    export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
    os.makedirs(export_dir, exist_ok=True)
    filename = f"export_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(export_dir, filename)

    queryset, headers = None, []
    if data_type == "sessions":
        queryset = Session.objects.all().order_by("-start_time")
        headers = ["ID", "Utilisateur", "Début", "Fin", "Durée", "Appareil", "Localisation"]
    elif data_type == "chatbot":
        queryset = ChatbotInteraction.objects.all().order_by("-created_at")
        headers = ["ID", "Question", "Réponse", "Satisfaction", "Date", "Session ID"]
    elif data_type == "products":
        queryset = Product.objects.all().order_by("name")
        headers = ["ID", "Nom", "Catégorie", "Prix", "Disponible", "Marque"]

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for obj in queryset:
            if data_type == "sessions":
                writer.writerow([
                    obj.id, obj.user_id or "visiteur",
                    obj.start_time.strftime("%d/%m/%Y %H:%M"),
                    obj.end_time.strftime("%d/%m/%Y %H:%M") if obj.end_time else "-",
                    str(obj.duration or "-"),
                    obj.device or "-", obj.location or "-"
                ])
            elif data_type == "chatbot":
                writer.writerow([
                    obj.id, obj.question[:80], obj.response[:80] if obj.response else "-",
                    "Oui" if obj.satisfaction else "Non",
                    obj.created_at.strftime("%d/%m/%Y %H:%M"),
                    obj.session.id if obj.session else "-"
                ])
            elif data_type == "products":
                writer.writerow([
                    obj.id, obj.name, obj.category or "-", obj.price,
                    "Oui" if obj.available else "Non", obj.brand or "-"
                ])

    ExportHistory.objects.create(
        export_type=data_type,
        file_path=f"/media/exports/{filename}",
        exported_at=datetime.now(),
        user=str(request.user) if request.user.is_authenticated else "Système"
    )

    return JsonResponse({"success": True, "file": f"/media/exports/{filename}"})


@role_required(Role.ADMIN)
@login_required
def users_management(request):
    return render(request, "dashboard/includes/users_management.html")
