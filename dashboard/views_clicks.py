
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


def clicks_view(request):
    """
    Vue complète des consultations produits avec statistiques par source.
    Utilise ProductView pour tracker tous les clics (chatbot, carte, recherche).
    Exclut les clics sur zones sans produit (product=None).
    """
    # Récupérer toutes les consultations de produits (exclure les clics zones)
    product_views = ProductView.objects.filter(product__isnull=False).select_related("session", "product").order_by("-viewed_at")

    # Filtrage par source si demandé
    source_filter = request.GET.get("source")
    if source_filter and source_filter in ["chatbot", "carte", "recherche"]:
        product_views = product_views.filter(source=source_filter)

    # Statistiques globales (uniquement consultations de produits)
    total_clicks = ProductView.objects.filter(product__isnull=False).count()
    clicks_chatbot = ProductView.objects.filter(product__isnull=False, source="chatbot").count()
    clicks_carte = ProductView.objects.filter(product__isnull=False, source="carte").count()
    clicks_recherche = ProductView.objects.filter(product__isnull=False, source="recherche").count()

    # Calcul des pourcentages
    pct_chatbot = round((clicks_chatbot / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_carte = round((clicks_carte / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_recherche = round((clicks_recherche / total_clicks * 100), 1) if total_clicks > 0 else 0

    # Taux de conversion des recommandations chatbot
    from dashboard.models import ChatbotRecommendation
    total_recommendations = ChatbotRecommendation.objects.count()
    clicked_recommendations = ChatbotRecommendation.objects.filter(clicked=True).count()
    not_clicked_recommendations = total_recommendations - clicked_recommendations
    conversion_rate = round((clicked_recommendations / total_recommendations * 100), 1) if total_recommendations > 0 else 0

    # ========== STATISTIQUES ZONES ==========
    # Tous les clics zones (product=None)
    from dashboard.zone_mapping import get_zone_name

    zone_clicks = ProductView.objects.filter(product__isnull=True)
    total_zone_clicks = zone_clicks.count()

    # Top 10 zones les plus explorées
    top_zones_raw = (
        zone_clicks.exclude(zone__isnull=True).exclude(zone='')
        .values('zone')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Convertir les IDs zones en noms descriptifs pour l'affichage
    top_zones = [
        {
            'zone': item['zone'],  # Garder l'ID original
            'zone_name': get_zone_name(item['zone']),  # Ajouter le nom
            'count': item['count']
        }
        for item in top_zones_raw
    ]

    # Sessions ayant exploré au moins une zone
    sessions_with_zones = zone_clicks.values('session').distinct().count()

    # Taux d'exploration (% des sessions qui ont cliqué sur la carte)
    from dashboard.models import Session
    total_sessions = Session.objects.count()
    zone_exploration_rate = round((sessions_with_zones / total_sessions * 100), 1) if total_sessions > 0 else 0

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
        "not_clicked_recommendations": not_clicked_recommendations,
        "conversion_rate": conversion_rate,
        # Stats zones
        "total_zone_clicks": total_zone_clicks,
        "top_zones": top_zones,
        "sessions_with_zones": sessions_with_zones,
        "zone_exploration_rate": zone_exploration_rate,
    }

    return render(request, "dashboard/clicks.html", context)

def clicks_chart_data(request):
    """
    Données pour les graphiques de la page Clics.
    - Clics par jour (7 derniers jours)
    - Produits les plus consultés (top 5)
    - Répartition par source (chatbot, carte, recherche)
    - Top 10 zones explorées
    - Evolution des explorations zones
    Exclut les clics sur zones des stats produits.
    """
    today = timezone.now()
    start_date = today - timedelta(days=6)

    # 1. Consultations par jour (uniquement produits)
    clicks_per_day = (
        ProductView.objects.filter(product__isnull=False, viewed_at__date__gte=start_date.date())
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    labels = [c["day"].strftime("%d/%m") for c in clicks_per_day]
    values = [c["total"] for c in clicks_per_day]

    # 2. Top 5 produits les plus consultés
    top_products = (
        ProductView.objects.filter(product__isnull=False)
        .values("product__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # 3. Répartition par source (uniquement produits)
    clicks_by_source = {
        "chatbot": ProductView.objects.filter(product__isnull=False, source="chatbot").count(),
        "carte": ProductView.objects.filter(product__isnull=False, source="carte").count(),
        "recherche": ProductView.objects.filter(product__isnull=False, source="recherche").count(),
    }

    # 4. Top 10 zones les plus explorées
    from dashboard.zone_mapping import get_zone_name

    top_zones_raw = (
        ProductView.objects.filter(product__isnull=True)
        .exclude(zone__isnull=True).exclude(zone='')
        .values('zone')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )

    # Convertir les IDs zones en noms descriptifs
    top_zones = [
        {
            'zone': get_zone_name(item['zone']),
            'total': item['total']
        }
        for item in top_zones_raw
    ]

    # 5. Clics zones par jour (7 derniers jours)
    zone_clicks_per_day = (
        ProductView.objects.filter(product__isnull=True, viewed_at__date__gte=start_date.date())
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    zone_labels = [c["day"].strftime("%d/%m") for c in zone_clicks_per_day]
    zone_values = [c["total"] for c in zone_clicks_per_day]

    return JsonResponse({
        "labels": labels,
        "clicks_per_day": values,
        "labels_types": [p["product__name"] for p in top_products],
        "clicks_by_label": [p["total"] for p in top_products],
        "clicks_by_source": clicks_by_source,
        # Données zones
        "top_zones_labels": [z["zone"] for z in top_zones],
        "top_zones_values": [z["total"] for z in top_zones],
        "zone_labels": zone_labels,
        "zone_clicks_per_day": zone_values,
    })
