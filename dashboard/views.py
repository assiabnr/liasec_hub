import csv
import os
import re
from datetime import timedelta, date, datetime

from django.core.paginator import Paginator
from django.db.models import Count, Avg, Sum, DurationField, Value
from django.db.models.functions import TruncDate, Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from dashboard.models import Session, Click, ProductView, ChatbotInteraction, ExportHistory

from django.shortcuts import render, redirect
from django.contrib import messages
from dashboard.models import Settings, ChatbotInteraction
from liasec_hub import settings

from django.contrib.auth.decorators import login_required
from accounts.models import Role
from accounts.decorators import role_required


# ==========================
# VUE D’ACCUEIL DU DASHBOARD
# ==========================
def dashboard_home(request):
    context = {
        "sessions_count": Session.objects.count(),
        "clicks_count": Click.objects.count(),
        "products_count": ProductView.objects.count(),
        "chatbot_count": ChatbotInteraction.objects.count(),
    }
    return render(request, "dashboard/dashboard_home.html", context)


# ==========================
# DONNÉES GRAPHIQUE PRINCIPAL
# ==========================
def chart_data(request):
    labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    today = timezone.now()
    start_of_week = today - timedelta(days=today.weekday())

    sessions_data = []
    clicks_data = []

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        sessions_count = Session.objects.filter(start_time__date=day.date()).count()
        clicks_count = Click.objects.filter(timestamp__date=day.date()).count()
        sessions_data.append(sessions_count)
        clicks_data.append(clicks_count)

    data = {"labels": labels, "sessions": sessions_data, "clicks": clicks_data}
    return JsonResponse(data)


# ==========================
# SESSIONS
# ==========================

def sessions_view(request):
    sessions = Session.objects.prefetch_related("clicks", "chatbot_interactions").order_by("-start_time")

    paginator = Paginator(sessions, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    #Agrégations
    total_sessions = sessions.count()
    total_duration = sessions.aggregate(
        total=Coalesce(Sum("duration", output_field=DurationField()), Value(timedelta(0), output_field=DurationField()))
    )["total"]

    avg_duration = sessions.aggregate(
        avg=Avg("duration")
    )["avg"]

    total_chatbot_interactions = ChatbotInteraction.objects.count()
    total_clicks = Click.objects.count()

    # Helper formatage durée
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
        else:
            return f"{seconds}s"


    context = {
        "sessions": page_obj,
        "total_sessions": total_sessions,
        "total_duration": format_duration(total_duration),
        "avg_duration": format_duration(avg_duration),
        "total_chatbot_interactions": total_chatbot_interactions,
        "total_clicks": total_clicks,
    }
    return render(request, "dashboard/sessions.html", context)


def session_detail_view(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    clicks = session.clicks.all()
    chats = session.chatbot_interactions.all()
    products = session.product_views.all()
    return render(
        request,
        "dashboard/includes/_session_detail.html",
        {"session": session, "clicks": clicks, "chats": chats, "products": products},
    )


# ==========================
# CLICS
# ==========================
def clicks_view(request):
    clicks = Click.objects.select_related("session").order_by("-timestamp")

    paginator = Paginator(clicks, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "dashboard/clicks.html", {"clicks": page_obj})


def clicks_chart_data(request):
    today = timezone.now()
    start_date = today - timezone.timedelta(days=6)

    clicks_per_day = (
        Click.objects.filter(timestamp__date__gte=start_date.date())
        .annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    labels = [c["day"].strftime("%d/%m") for c in clicks_per_day]
    values = [c["total"] for c in clicks_per_day]

    clicks_by_label = (
        Click.objects.values("page")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    data = {
        "labels": labels,
        "clicks_per_day": values,
        "labels_types": [c["page"] for c in clicks_by_label],
        "clicks_by_label": [c["total"] for c in clicks_by_label],
    }
    return JsonResponse(data)


# ==========================
#  PRODUITS
# ==========================
def produits_view(request):
    """
    Vue principale du tableau Produits
    - Clics : uniquement ceux venant de la carte (source='carte')
    - Recos : produits mentionnés dans les réponses du chatbot
    """

    # --- Produits consultés via la carte ---
    product_views = (
        ProductView.objects.filter(source="carte")  # 🔹 <--- ici la clé
        .values("product_name", "product_id")
        .annotate(clicks=Count("id"))
    )

    # --- Produits recommandés par le chatbot ---
    chatbot_reco = (
        ChatbotInteraction.objects
        .filter(response__isnull=False)
        .values("response")
        .annotate(recos=Count("id"))
    )

    # --- Association approximative par nom ---
    chatbot_dict = {}
    for c in chatbot_reco:
        text = c["response"].lower()
        for pv in product_views:
            name = pv["product_name"].lower()
            if re.search(rf"\b{name.split()[0]}\b", text):
                chatbot_dict[name] = chatbot_dict.get(name, 0) + c["recos"]

    # --- Fusion finale ---
    formatted_products = []
    for p in product_views:
        name = p["product_name"]
        formatted_products.append({
            "name": name,
            "ref": p["product_id"],
            "category": "—",
            "clicks": p["clicks"],
            "chatbot_interactions": chatbot_dict.get(name.lower(), 0),
        })

    formatted_products.sort(key=lambda x: x["clicks"], reverse=True)

    # --- Pagination ---
    paginator = Paginator(formatted_products, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "dashboard/produits.html", {"products": page_obj})


def products_chart_data(request):
    """
    Données pour le graphique Produits :
    - Clics réels sur la carte
    - Recommandations chatbot
    """

    # --- Produits cliqués sur la carte ---
    product_views = (
        ProductView.objects.filter(source="carte")  # 🔹 clé : clics réels via carte
        .values("product_name")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:15]
    )

    # --- Produits mentionnés par le chatbot ---
    chatbot_reco = (
        ChatbotInteraction.objects
        .filter(response__isnull=False)
        .values("response")
        .annotate(recos=Count("id"))
    )

    # ---  Fusion intelligente ---
    chatbot_dict = {}
    for c in chatbot_reco:
        text = c["response"].lower()
        for pv in product_views:
            name = pv["product_name"].lower()
            if re.search(rf"\b{name.split()[0]}\b", text):
                chatbot_dict[name] = chatbot_dict.get(name, 0) + c["recos"]

    # --- Format JSON ---
    products_data = []
    for p in product_views:
        name = p["product_name"].strip()
        products_data.append({
            "name": name,
            "clicks": p["clicks"],
            "chatbot": chatbot_dict.get(name.lower(), 0),
        })

    products_data.sort(key=lambda x: x["clicks"], reverse=True)

    return JsonResponse({
        "products": products_data,
        "meta": {
            "source_clicks": "ProductView (source=carte)",
            "source_chatbot": "ChatbotInteraction.response",
            "total_products": len(products_data)
        }
    })


# ==========================
# CHATBOT
# ==========================
def chatbot_view(request):
    total_interactions = ChatbotInteraction.objects.count()
    total_sessions = Session.objects.count()
    sessions_with_chatbot = (
        Session.objects.filter(chatbot_interactions__isnull=False)
        .distinct().count()
    )

    chatbot_session_rate = round((sessions_with_chatbot / total_sessions * 100), 1) if total_sessions > 0 else 0

    satisfied_count = ChatbotInteraction.objects.filter(satisfaction=True).count()
    avg_satisfaction = round((satisfied_count / total_interactions * 100), 1) if total_interactions > 0 else 0

    interactions_list = ChatbotInteraction.objects.order_by("-created_at")
    paginator = Paginator(interactions_list, 25)
    page_number = request.GET.get("page")
    interactions = paginator.get_page(page_number)

    context = {
        "total_interactions": total_interactions,
        "chatbot_session_rate": chatbot_session_rate,
        "avg_satisfaction": avg_satisfaction,
        "interactions": interactions,
    }

    return render(request, "dashboard/chatbot.html", context)


def chatbot_chart_data(request):
    today = timezone.now()
    labels = []
    interactions_per_day = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%d/%m"))
        count = ChatbotInteraction.objects.filter(created_at__date=day.date()).count()
        interactions_per_day.append(count)

    top_products = (
        ChatbotInteraction.objects.values("response")
        .exclude(response__isnull=True)
        .exclude(response__exact="")
        .annotate(total=Count("id"))
        .order_by("-total")[:6]
    )

    data = {
        "labels": labels,
        "interactions_per_day": interactions_per_day,
        "top_products": {
            "labels": [p["response"][:25] + "..." for p in top_products],
            "values": [p["total"] for p in top_products],
        },
    }

    return JsonResponse(data)



def settings_view(request):
    # Récupère ou crée la configuration unique
    settings, _ = Settings.objects.get_or_create(id=1)

    if request.method == "POST":
        action = request.POST.get("action")

        # Sauvegarde des paramètres
        if action == "save":
            settings.name = request.POST.get("name", settings.name)
            settings.location = request.POST.get("location", settings.location)
            settings.code = request.POST.get("code", settings.code)
            settings.track_sessions = request.POST.get("track_sessions") == "on"
            settings.track_clicks = request.POST.get("track_clicks") == "on"
            settings.track_chatbot = request.POST.get("track_chatbot") == "on"
            settings.save()
            messages.success(request, "Paramètres sauvegardés avec succès.")
            return redirect("settings")

        # Réinitialisation des données
        elif action == "reset":
            Session.objects.all().delete()
            Click.objects.all().delete()
            ChatbotInteraction.objects.all().delete()
            messages.warning(request, "Toutes les données ont été réinitialisées.")
            return redirect("settings")

    return render(request, "dashboard/settings.html", {"settings": settings})

@csrf_exempt
def reset_data_view(request):
    if request.method == "POST":
        # Suppression de toutes les données principales
        Session.objects.all().delete()
        Click.objects.all().delete()
        ChatbotInteraction.objects.all().delete()
        ProductView.objects.all().delete()
        ExportHistory.objects.all().delete()

        return JsonResponse({"success": True, "message": "Toutes les données ont été réinitialisées."})
    return JsonResponse({"success": False, "error": "Méthode non autorisée."}, status=405)


def export_history_view(request):
    settings = Settings.objects.first()
    if not settings:
        return HttpResponse("Aucune configuration trouvée.", content_type="text/plain")

    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="configuration_liasec.csv"'

    writer = csv.writer(response)
    writer.writerow(["Nom de la borne", "Localisation", "Code", "Suivi sessions", "Suivi clics", "Suivi chatbot", "Dernière mise à jour"])
    writer.writerow([
        settings.name,
        settings.location,
        settings.code,
        "Oui" if settings.track_sessions else "Non",
        "Oui" if settings.track_clicks else "Non",
        "Oui" if settings.track_chatbot else "Non",
        settings.updated_at.strftime("%d/%m/%Y %H:%M")
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
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    product_name = request.POST.get("product_name")

    if not data_type:
        return JsonResponse({"success": False, "error": "Type de données manquant."}, status=400)

    # Dossier d'export
    export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
    os.makedirs(export_dir, exist_ok=True)

    # Nom de fichier
    filename = f"export_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(export_dir, filename)

    # Application des filtres
    queryset = None
    if data_type == "sessions":
        queryset = Session.objects.all().order_by("-start_time")
        headers = ["ID", "Utilisateur", "Début", "Fin", "Durée", "Appareil", "Localisation"]

    elif data_type == "clicks":
        queryset = Click.objects.all().order_by("-timestamp")
        headers = ["ID", "Produit", "Page", "Date du clic", "Session ID"]

    elif data_type == "products":
        queryset = ProductView.objects.all().order_by("-viewed_at")
        headers = ["ID", "Produit", "Zone", "Source", "Date", "Session ID"]

    elif data_type == "chatbot":
        queryset = ChatbotInteraction.objects.all().order_by("-created_at")
        headers = ["ID", "Question", "Réponse", "Satisfaction", "Date", "Session ID"]

    else:
        return JsonResponse({"success": False, "error": "Type de données invalide."}, status=400)

    # Filtres temporels
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date) if hasattr(queryset.model, 'created_at') else queryset.filter(start_time__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date) if hasattr(queryset.model, 'created_at') else queryset.filter(start_time__lte=end_date)

    # Filtre produit (si applicable)
    if product_name and data_type in ["clicks", "products"]:
        queryset = queryset.filter(product_name__icontains=product_name)

    # Génération du CSV
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for obj in queryset:
            if data_type == "sessions":
                writer.writerow([
                    obj.id,
                    obj.user_id or "visiteur",
                    obj.start_time.strftime("%d/%m/%Y %H:%M") if obj.start_time else "",
                    obj.end_time.strftime("%d/%m/%Y %H:%M") if obj.end_time else "",
                    str(obj.duration or "-"),
                    obj.device or "-",
                    obj.location or "-"
                ])

            elif data_type == "clicks":
                writer.writerow([
                    obj.id,
                    obj.product_name or "-",
                    obj.page,
                    obj.timestamp.strftime("%d/%m/%Y %H:%M"),
                    obj.session.id if obj.session else "-"
                ])

            elif data_type == "products":
                writer.writerow([
                    obj.id,
                    obj.product_name,
                    obj.zone or "-",
                    obj.source or "-",
                    obj.viewed_at.strftime("%d/%m/%Y %H:%M"),
                    obj.session.id if obj.session else "-"
                ])

            elif data_type == "chatbot":
                writer.writerow([
                    obj.id,
                    obj.question[:80].replace("\n", " "),
                    (obj.response[:100] + "...") if obj.response and len(obj.response) > 100 else (obj.response or "-"),
                    "Oui" if obj.satisfaction else "Non",
                    obj.created_at.strftime("%d/%m/%Y %H:%M"),
                    obj.session.id if obj.session else "-"
                ])

    # Enregistrement dans l’historique
    ExportHistory.objects.create(
        export_type=data_type,
        file_path=f"/media/exports/{filename}",
        exported_at=datetime.now(),
        user=str(request.user) if request.user.is_authenticated else "Système"
    )

    return JsonResponse({
        "success": True,
        "message": f"Fichier {filename} généré avec succès.",
        "file": f"/media/exports/{filename}"
    })


@role_required(Role.ADMIN)
@login_required
def users_management(request):
    return render(request, "dashboard/includes/users_management.html")