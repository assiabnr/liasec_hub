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
    context = {
        "sessions_count": Session.objects.count(),
        "clicks_count": Click.objects.count(),
        "products_count": Product.objects.count(),
        "chatbot_count": ChatbotInteraction.objects.count(),
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
    """
    sessions = (
        Session.objects.prefetch_related("clicks", "chatbot_interactions")
        .order_by("-start_time")
    )

    paginator = Paginator(sessions, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Totaux
    total_sessions = sessions.count()
    total_duration = sessions.aggregate(
        total=Coalesce(Sum("duration", output_field=DurationField()), Value(timedelta(0)))
    )["total"]
    avg_duration = sessions.aggregate(avg=Avg("duration"))["avg"]
    total_chatbot_interactions = ChatbotInteraction.objects.count()
    total_clicks = Click.objects.count()

    # Sessions avec au moins une interaction chatbot
    sessions_with_chatbot = Session.objects.filter(chatbot_interactions__isnull=False).distinct().count()
    chatbot_session_rate = round((sessions_with_chatbot / total_sessions * 100), 1) if total_sessions else 0

    # Satisfaction globale (Oui / Non)
    feedbacks = ChatbotInteraction.objects.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    total_feedbacks = feedbacks.count()
    satisfaction_rate = round((satisfied / total_feedbacks * 100), 1) if total_feedbacks else 0

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
        "sessions": page_obj,
        "total_sessions": total_sessions,
        "total_duration": format_duration(total_duration),
        "avg_duration": format_duration(avg_duration),
        "total_chatbot_interactions": total_chatbot_interactions,
        "total_clicks": total_clicks,
        "chatbot_session_rate": chatbot_session_rate,
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "total_feedbacks": total_feedbacks,
    }

    return render(request, "dashboard/sessions.html", context)


def session_detail_view(request, session_id):
    """
    Détail d’une session : clics, interactions chatbot, produits consultés.
    """
    session = get_object_or_404(Session, id=session_id)
    clicks = session.clicks.all().order_by("timestamp")
    chats = session.chatbot_interactions.all().order_by("created_at")
    products = session.product_views.select_related("product").order_by("viewed_at")

    # Calcul d’un petit résumé de satisfaction pour cette session
    feedbacks = chats.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    total_feedbacks = feedbacks.count()
    satisfaction_rate = round((satisfied / total_feedbacks * 100), 1) if total_feedbacks else None

    context = {
        "session": session,
        "clicks": clicks,
        "chats": chats,
        "products": products,
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "total_feedbacks": total_feedbacks,
    }

    return render(request, "dashboard/includes/_session_detail.html", context)


# ==========================
# CLICS
# ==========================
def clicks_view(request):
    clicks = Click.objects.select_related("session").order_by("-timestamp")
    paginator = Paginator(clicks, 20)
    return render(request, "dashboard/clicks.html", {"clicks": paginator.get_page(request.GET.get("page"))})


def clicks_chart_data(request):
    today = timezone.now()
    start_date = today - timedelta(days=6)

    clicks_per_day = (
        Click.objects.filter(timestamp__date__gte=start_date.date())
        .annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    labels = [c["day"].strftime("%d/%m") for c in clicks_per_day]
    values = [c["total"] for c in clicks_per_day]

    top_pages = (
        Click.objects.values("page").annotate(total=Count("id")).order_by("-total")[:5]
    )

    return JsonResponse({
        "labels": labels,
        "clicks_per_day": values,
        "labels_types": [p["page"] for p in top_pages],
        "clicks_by_label": [p["total"] for p in top_pages],
    })


# ==========================
# PRODUITS
# ==========================
def produits_view(request):
    """
    Tableau de bord Produits
    Analyse visibilité, performance et disponibilité des produits.
    """

    # ========== INDICATEURS GLOBAUX ==========

    total_products = Product.objects.count()
    available_products = Product.objects.filter(available=True).count()
    unavailable_products = Product.objects.filter(available=False).count()

    total_views = ProductView.objects.count()
    total_recos = ChatbotRecommendation.objects.count()
    total_clicks = ProductView.objects.exclude(source__isnull=True).count()

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
        ProductView.objects.values("product__name", "product__id")
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
            click_rate=Coalesce(
                (100.0 * Count("chatbot_recommendations", filter=Q(chatbot_recommendations__clicked=True)) /
                 Count("chatbot_recommendations")),
                Value(0.0),
                output_field=FloatField()
            ),
        )
        .order_by("-total_views")
    )

    paginator = Paginator(all_products, 20)
    products_page = paginator.get_page(request.GET.get("page"))
    recos_dict = {r["product__name"]: r["recos"] for r in top_recommended}

    # ========== CONTEXTE ==========
    context = {
        # KPIs globaux
        "total_products": total_products,
        "available_products": available_products,
        "unavailable_products": unavailable_products,
        "total_views": total_views,
        "total_recos": total_recos,
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
    }

    return render(request, "dashboard/produits.html", context)



def products_chart_data(request):
    """
    Données JSON pour les graphiques produits (clics & recos)
    """
    top_views = (
        ProductView.objects.values("product__name")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:10]
    )

    top_recos = (
        ChatbotRecommendation.objects.values("product__name")
        .annotate(recos=Count("id"))
        .order_by("-recos")[:10]
    )

    return JsonResponse({
        "labels": [v["product__name"] for v in top_views],
        "clicks": [v["clicks"] for v in top_views],
        "recos": [
            next((r["recos"] for r in top_recos if r["product__name"] == v["product__name"]), 0)
            for v in top_views
        ],
    })



# ==========================
# CHATBOT
# ==========================


def chatbot_view(request):
    """
    Vue principale du tableau de bord Chatbot :
    Affiche les statistiques globales, les analyses NLP,
    et l’historique des produits recommandés.
    """

    # ========== STATISTIQUES GLOBALES ==========
    total_interactions = ChatbotInteraction.objects.count()
    total_sessions = Session.objects.count()
    sessions_with_chatbot = (
        Session.objects.filter(chatbot_interactions__isnull=False)
        .distinct()
        .count()
    )
    chatbot_session_rate = round(
        (sessions_with_chatbot / total_sessions * 100), 1
    ) if total_sessions else 0

    # Taux de réponse réussie et fallback
    success_count = ChatbotInteraction.objects.filter(response_success=True).count()
    fallback_count = ChatbotInteraction.objects.filter(response_success=False).count()
    success_rate = round((success_count / total_interactions * 100), 1) if total_interactions else 0
    fallback_rate = round((fallback_count / total_interactions * 100), 1) if total_interactions else 0

    # Temps de réponse moyen
    avg_response_time = ChatbotInteraction.objects.aggregate(avg=Avg("response_time"))["avg"]
    avg_response_time = round(avg_response_time or 0, 2)

    # ========== TAUX DE SATISFACTION ==========
    feedbacks = ChatbotInteraction.objects.filter(satisfaction__isnull=False)
    satisfied = feedbacks.filter(satisfaction=True).count()
    unsatisfied = feedbacks.filter(satisfaction=False).count()
    total_feedbacks = feedbacks.count()
    satisfaction_rate = round((satisfied / total_feedbacks * 100), 1) if total_feedbacks else 0

    # ========== RECOMMANDATIONS PRODUITS ==========
    total_recommendations = ChatbotRecommendation.objects.count()
    clicked_recos = ChatbotRecommendation.objects.filter(clicked=True).count()
    click_rate = round((clicked_recos / total_recommendations * 100), 1) if total_recommendations else 0

    top_products = (
        ChatbotRecommendation.objects.values("product__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # ========== ANALYSE NLP / INTENTIONS ==========
    top_intents = (
        ChatbotInteraction.objects
        .annotate(intent_lower=Lower("intent"))  # ✅ pas de conflit
        .values("intent_lower")  # on utilise l'alias
        .annotate(
            total=Count("id"),
            success_rate=Coalesce(
                Avg("response_success", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ),
            satisfaction_rate=Coalesce(
                Avg("satisfaction", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ),
        )
        .exclude(intent_lower__isnull=True)
        .order_by("-total")[:10]
    )

    worst_intents = (
        ChatbotInteraction.objects
        .annotate(intent_lower=Lower("intent"))
        .values("intent_lower")
        .annotate(
            total=Count("id"),
            failure_rate=1 - Coalesce(
                Avg("response_success", output_field=FloatField()),
                Value(0.0),
                output_field=FloatField()
            ),
        )
        .exclude(intent_lower__isnull=True)
        .order_by("-failure_rate")[:5]
    )

    # ========== ÉVOLUTION TEMPORELLE ==========
    today = timezone.now()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels, interactions_data, response_time_data = [], [], []

    for day in last_7_days:
        labels.append(day.strftime("%d/%m"))
        day_interactions = ChatbotInteraction.objects.filter(created_at__date=day.date())
        interactions_data.append(day_interactions.count())
        avg_time = day_interactions.aggregate(avg=Avg("response_time"))["avg"]
        response_time_data.append(round(avg_time or 0, 2))

    # ========== HISTORIQUE DES RECOMMANDATIONS ==========
    recommendations_qs = (
        ChatbotRecommendation.objects
        .select_related("session", "interaction", "product")
        .order_by("-recommended_at")
    )
    paginator = Paginator(recommendations_qs, 25)
    recommendations = paginator.get_page(request.GET.get("page"))

    # ========== CONTEXTE ==========
    context = {
        "total_interactions": total_interactions,
        "total_sessions": total_sessions,
        "chatbot_session_rate": chatbot_session_rate,
        "success_rate": success_rate,
        "fallback_rate": fallback_rate,
        "avg_response_time": avg_response_time,
        "satisfaction_rate": satisfaction_rate,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "total_feedbacks": total_feedbacks,
        "total_recommendations": total_recommendations,
        "click_rate": click_rate,
        "top_products": top_products,
        "recommendations": recommendations,
        "top_intents": top_intents,
        "worst_intents": worst_intents,
        "chart_labels": labels,
        "chart_interactions": interactions_data,
        "chart_response_time": response_time_data,
    }

    return render(request, "dashboard/chatbot.html", context)

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
