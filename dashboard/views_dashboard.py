
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
from .cache_utils import cache_dashboard_kpis
from .utils.analytics import calculate_trend, get_period_comparison, get_kpi_with_trend


@cache_dashboard_kpis(timeout=300)  # Cache pour 5 minutes
def calculate_dashboard_kpis():
    """
    Calcule tous les KPIs du dashboard principal.
    Cette fonction est cachée pour améliorer les performances.
    """
    from django.db.models.functions import TruncDate, Cast
    from django.db.models import Avg, Sum, F, Q, FloatField
    import json

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

    # Taux de satisfaction (uniquement pour les interactions avec feedback)
    satisfaction_stats = ChatbotInteraction.objects.filter(
        satisfaction__isnull=False
    ).aggregate(
        total=Count('id'),
        positives=Count('id', filter=Q(satisfaction=True))
    )

    satisfaction_total = satisfaction_stats['total'] or 0
    satisfaction_positives = satisfaction_stats['positives'] or 0
    satisfaction_rate = round((satisfaction_positives / satisfaction_total * 100), 1) if satisfaction_total > 0 else 0

    # Taux de succès
    success_stats = ChatbotInteraction.objects.aggregate(
        total=Count('id'),
        successes=Count('id', filter=Q(response_success=True))
    )
    success_total = success_stats['total'] or 0
    success_count = success_stats['successes'] or 0
    success_rate = round((success_count / success_total * 100), 1) if success_total > 0 else 0

    # Temps de réponse moyen
    avg_response_time = ChatbotInteraction.objects.filter(
        response_time__isnull=False
    ).aggregate(avg_time=Avg('response_time'))['avg_time']
    avg_response_time = round(avg_response_time, 2) if avg_response_time else 0

    # ========== PRODUITS ==========
    products_total = Product.objects.count()
    products_available = Product.objects.filter(available=True).count()

    # Top 5 intents
    top_intents = list(
        ChatbotInteraction.objects.filter(intent__isnull=False)
        .exclude(intent='')
        .values('intent')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Top 5 produits consultés
    top_products_raw = list(
        ProductView.objects.filter(product__isnull=False)
        .values('product__name', 'product__price')
        .annotate(views=Count('id'))
        .order_by('-views')[:5]
    )
    top_products = [
        {'name': p['product__name'], 'views': p['views'], 'price': float(p['product__price'])}
        for p in top_products_raw
    ]

    # Sources de clics
    sources = list(
        ProductView.objects.exclude(source__isnull=True).exclude(source='')
        .values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Graphique 7 jours (sessions par jour)
    sessions_by_day = list(
        Session.objects.filter(start_time__gte=last_7_days)
        .annotate(day=TruncDate('start_time'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # Total clics
    clicks_total = ProductView.objects.count()

    # Prix moyen consulté
    avg_price_viewed = ProductView.objects.filter(
        product__isnull=False
    ).aggregate(
        avg_price=Avg('product__price')
    )['avg_price']
    avg_price_viewed = round(float(avg_price_viewed), 2) if avg_price_viewed else 0

    # Recommandations
    recommendations_total = ChatbotRecommendation.objects.count()
    recommendations_clicked = ChatbotRecommendation.objects.filter(clicked=True).count()
    recommendations_ctr = round((recommendations_clicked / recommendations_total * 100), 1) if recommendations_total > 0 else 0

    # ========== TENDANCES UNIFORMISÉES ==========
    # Calculer les tendances pour les KPIs principaux
    sessions_trend = calculate_trend(sessions_last_7, sessions_previous_7)

    # Interactions chatbot - comparaison période précédente
    interactions_previous_7 = ChatbotInteraction.objects.filter(
        created_at__gte=previous_7_days, created_at__lt=last_7_days
    ).count()
    interactions_trend = calculate_trend(interactions_last_7, interactions_previous_7)

    # Clics - comparaison période précédente
    clicks_last_7 = ProductView.objects.filter(viewed_at__gte=last_7_days).count()
    clicks_previous_7 = ProductView.objects.filter(
        viewed_at__gte=previous_7_days, viewed_at__lt=last_7_days
    ).count()
    clicks_trend = calculate_trend(clicks_last_7, clicks_previous_7)

    # Satisfaction - comparaison période précédente
    satisfaction_last_7_stats = ChatbotInteraction.objects.filter(
        created_at__gte=last_7_days,
        satisfaction__isnull=False
    ).aggregate(
        total=Count('id'),
        positives=Count('id', filter=Q(satisfaction=True))
    )
    satisfaction_previous_7_stats = ChatbotInteraction.objects.filter(
        created_at__gte=previous_7_days,
        created_at__lt=last_7_days,
        satisfaction__isnull=False
    ).aggregate(
        total=Count('id'),
        positives=Count('id', filter=Q(satisfaction=True))
    )

    sat_last_total = satisfaction_last_7_stats['total'] or 0
    sat_last_positives = satisfaction_last_7_stats['positives'] or 0
    sat_last_rate = (sat_last_positives / sat_last_total * 100) if sat_last_total > 0 else 0

    sat_prev_total = satisfaction_previous_7_stats['total'] or 0
    sat_prev_positives = satisfaction_previous_7_stats['positives'] or 0
    sat_prev_rate = (sat_prev_positives / sat_prev_total * 100) if sat_prev_total > 0 else 0

    satisfaction_trend = calculate_trend(sat_last_rate, sat_prev_rate)

    return {
        'sessions_total': sessions_total,
        'sessions_last_7': sessions_last_7,
        'sessions_variation': sessions_variation,
        'sessions_trend': sessions_trend,  # Nouveau format unifié
        'avg_duration_minutes': avg_duration_minutes,
        'active_sessions_rate': active_sessions_rate,
        'interactions_total': interactions_total,
        'interactions_last_7': interactions_last_7,
        'interactions_trend': interactions_trend,  # Nouveau
        'satisfaction_rate': satisfaction_rate,
        'satisfaction_trend': satisfaction_trend,  # Nouveau
        'success_rate': success_rate,
        'avg_response_time': avg_response_time,
        'products_total': products_total,
        'products_available': products_available,
        'top_intents': top_intents,
        'top_products': top_products,
        'sources': sources,
        'sessions_by_day': sessions_by_day,
        'clicks_total': clicks_total,
        'clicks_trend': clicks_trend,  # Nouveau
        'avg_price_viewed': avg_price_viewed,
        'recommendations_total': recommendations_total,
        'recommendations_ctr': recommendations_ctr,
    }


def dashboard_home(request):
    import json

    # ========== RÉCUPÉRATION DES KPIS CACHÉS ==========
    kpis = calculate_dashboard_kpis()

    # Déstructurer pour le template (pour compatibilité avec l'ancien code)
    sessions_total = kpis['sessions_total']
    sessions_last_7 = kpis['sessions_last_7']
    sessions_variation = kpis['sessions_variation']
    avg_duration_minutes = kpis['avg_duration_minutes']
    active_sessions_rate = kpis['active_sessions_rate']
    interactions_total = kpis['interactions_total']
    interactions_last_7 = kpis['interactions_last_7']
    satisfaction_rate = kpis['satisfaction_rate']
    success_rate = kpis['success_rate']
    avg_response_time = kpis['avg_response_time']
    products_total = kpis['products_total']
    products_available = kpis['products_available']
    top_intents = kpis['top_intents']
    top_products = kpis['top_products']
    sources = kpis['sources']
    sessions_by_day = kpis['sessions_by_day']
    clicks_total = kpis['clicks_total']
    avg_price_viewed = kpis['avg_price_viewed']
    recommendations_total = kpis['recommendations_total']
    recommendations_ctr = kpis['recommendations_ctr']

    # Code legacy (peut être supprimé si tout est dans kpis)
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

    # Taux de satisfaction et répartition des feedbacks (incluant les conversations sans retour)
    feedback_qs = ChatbotInteraction.objects.filter(ask_feedback=True)
    satisfaction_agg = feedback_qs.aggregate(
        positive=Count("id", filter=Q(satisfaction=True)),
        negative=Count("id", filter=Q(satisfaction=False)),
        no_return=Count("id", filter=Q(satisfaction__isnull=True)),
        answered=Count("id", filter=Q(satisfaction__isnull=False)),
    )
    total_with_feedback_option = feedback_qs.count()
    satisfaction_rate = round((satisfaction_agg["positive"] / total_with_feedback_option * 100), 1) if total_with_feedback_option else 0

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

    # ========== CLICS (basés sur les consultations produits) ==========
    clicks_total = product_views_total
    clicks_last_7 = product_views_last_7
    clicks_previous_7 = product_views_previous_7
    clicks_variation = product_views_variation

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
    sources_data = ProductView.objects.values("source").annotate(
        count=Count("id")
    ).order_by("-count")

    # ========== ÉVOLUTION 7 DERNIERS JOURS ==========
    start_range = (today - timedelta(days=6)).date()
    end_range = today.date()

    def build_daily_counts(qs, field_name):
        truncated = qs.filter(**{f"{field_name}__date__gte": start_range, f"{field_name}__date__lte": end_range})
        aggregated = (
            truncated
            .annotate(day=TruncDate(field_name))
            .values("day")
            .annotate(count=Count("id"))
        )
        return {entry["day"]: entry["count"] for entry in aggregated}

    sessions_by_day = build_daily_counts(Session.objects, "start_time")
    interactions_by_day = build_daily_counts(ChatbotInteraction.objects, "created_at")
    views_by_day = build_daily_counts(ProductView.objects, "viewed_at")
    clicks_by_day = views_by_day  # legacy naming, aligné sur les consultations produits

    evolution_data = []
    for i in range(6, -1, -1):
        day = (today - timedelta(days=i)).date()
        evolution_data.append({
            "date": day.strftime("%d/%m"),
            "sessions": sessions_by_day.get(day, 0),
            "interactions": interactions_by_day.get(day, 0),
            "product_views": views_by_day.get(day, 0),
            "clicks": clicks_by_day.get(day, 0),
        })

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
        "satisfied_feedbacks": satisfaction_agg["positive"],
        "unsatisfied_feedbacks": satisfaction_agg["negative"],
        "no_feedbacks": satisfaction_agg["no_return"],
        "total_feedbacks": satisfaction_agg["answered"],
        "total_feedback_requests": total_with_feedback_option,
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

    # Consultations produits : moyenne par jour de semaine
    clicks_qs = (
        ProductView.objects
        .annotate(day=ExtractWeekDay("viewed_at"))
        .values("day")
        .annotate(avg_clicks=Count("id") * 1.0 / Count("viewed_at__week", distinct=True))
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
