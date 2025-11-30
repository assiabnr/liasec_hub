
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
    not_clicked_recommendations = total_recommendations - clicked_recommendations
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
        "not_clicked_recommendations": not_clicked_recommendations,
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
