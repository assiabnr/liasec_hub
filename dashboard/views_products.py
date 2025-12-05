
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

    total_views = ProductView.objects.filter(product__isnull=False).count()
    total_recos = ChatbotRecommendation.objects.count()
    total_clicks = ProductView.objects.filter(product__isnull=False).exclude(source__isnull=True).count()

    # Vues uniques (par produit)
    unique_viewed_products = ProductView.objects.filter(product__isnull=False).values('product').distinct().count()

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
            ProductView.objects.filter(product__isnull=False, viewed_at__date=day.date()).count()
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
    # Top 10 produits les plus consultés (uniquement produits)
    top_views = (
        ProductView.objects.filter(product__isnull=False).values("product__name", "product__id")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    # Top 10 recommandations
    top_recos = (
        ChatbotRecommendation.objects.values("product__name", "product__id")
        .annotate(recos=Count("id"))
        .order_by("-recos")[:10]
    )

    # Vues par catégorie (uniquement produits)
    views_by_category = (
        ProductView.objects.filter(product__isnull=False).values("product__category")
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
            product__isnull=False,
            product__price__gte=pr["min"],
            product__price__lt=pr["max"]
        ).count()
        price_distribution.append(count)

    # Évolution vues produits (7 derniers jours, uniquement produits)
    today = timezone.now()
    views_7days_labels = []
    views_7days_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        views_7days_labels.append(day.strftime("%d/%m"))
        count = ProductView.objects.filter(product__isnull=False, viewed_at__date=day.date()).count()
        views_7days_data.append(count)

    # Sources de consultation des produits (uniquement produits)
    sources_distribution = (
        ProductView.objects.filter(product__isnull=False).values("source")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Préparer les données des sources
    sources_labels = []
    sources_data = []
    sources_colors = []

    source_mapping = {
        "chatbot": {"label": "Chatbot", "color": "#3B82F6"},
        "carte": {"label": "Carte Interactive", "color": "#F59E0B"},
        "recherche": {"label": "Recherche", "color": "#10B981"},
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
