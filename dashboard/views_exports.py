
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

from dashboard.pdf_exports import (
    generate_dashboard_pdf,
    generate_sessions_pdf,
    generate_chatbot_pdf,
    generate_products_pdf,
    generate_clicks_pdf
)


@login_required
def export_history_view(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès refusé.", status=403)
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

@login_required
def exports_view(request):
    is_admin = getattr(request.user, "role", None) == Role.ADMIN
    is_authorized = is_admin or getattr(request.user, "can_export", False)

    exports_qs = ExportHistory.objects.none()
    if is_authorized:
        exports_qs = ExportHistory.objects.all().order_by('-exported_at')
        if not is_admin:
            exports_qs = exports_qs.filter(user=str(request.user))

    exports = list(exports_qs[:20])

    managers = None
    pending_requests = None
    user_requests = None

    if is_admin:
        User = get_user_model()
        managers = User.objects.filter(role=Role.MANAGER, is_active=True).order_by("email")

        # Récupérer les demandes en attente pour l'admin
        from dashboard.models import ExportRequest
        pending_requests = ExportRequest.objects.filter(status='PENDING').select_related('requester').order_by('-requested_at')
    else:
        # Récupérer les demandes de l'utilisateur actuel (manager)
        from dashboard.models import ExportRequest
        user_requests = ExportRequest.objects.filter(requester=request.user).select_related('reviewed_by').order_by('-requested_at')

    return render(request, "dashboard/exports.html", {
        "exports": exports,
        "managers": managers,
        "is_authorized": is_authorized,
        "pending_requests": pending_requests,
        "user_requests": user_requests,
    })

@login_required
def export_data_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    # Autorisation : admin ou utilisateur explicitement autorisé
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return JsonResponse({"success": False, "error": "Accès réservé aux administrateurs ou utilisateurs autorisés."}, status=403)

    data_type = request.POST.get("data_type")
    export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
    os.makedirs(export_dir, exist_ok=True)

    start_raw = request.POST.get("start_date")
    end_raw = request.POST.get("end_date")
    start_date = end_date = None
    try:
        start_date = datetime.strptime(start_raw, "%Y-%m-%d") if start_raw else None
    except (TypeError, ValueError):
        start_date = None
    try:
        end_date = datetime.strptime(end_raw, "%Y-%m-%d") if end_raw else None
    except (TypeError, ValueError):
        end_date = None

    if data_type == "sessions":
        queryset = Session.objects.all().order_by("-start_time")
        if start_date:
            queryset = queryset.filter(start_time__date__gte=start_date.date())
        if end_date:
            queryset = queryset.filter(start_time__date__lte=end_date.date())
        headers = ["ID", "Utilisateur", "Début", "Fin", "Durée", "Appareil", "Localisation"]
    elif data_type == "chatbot":
        queryset = ChatbotInteraction.objects.all().order_by("-created_at")
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date.date())
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date.date())
        headers = ["ID", "Question", "Réponse", "Satisfaction", "Date", "Session ID"]
    elif data_type == "products":
        queryset = Product.objects.all().order_by("name")
        headers = ["ID", "Nom", "Catégorie", "Prix", "Disponible", "Marque"]
    elif data_type == "clicks":
        queryset = ProductView.objects.select_related("product", "session").order_by("-viewed_at")
        if start_date:
            queryset = queryset.filter(viewed_at__date__gte=start_date.date())
        if end_date:
            queryset = queryset.filter(viewed_at__date__lte=end_date.date())
        headers = ["ID", "Session", "Produit", "Source", "Zone", "Date"]
    else:
        return JsonResponse({"success": False, "error": "Type d'export non supporté."}, status=400)

    filename = f"export_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(export_dir, filename)

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
            elif data_type == "clicks":
                writer.writerow([
                    obj.id,
                    obj.session.id if obj.session else "-",
                    obj.product.name if obj.product else "-",
                    obj.source or "-",
                    obj.zone or "-",
                    obj.viewed_at.strftime("%d/%m/%Y %H:%M")
                ])

    ExportHistory.objects.create(
        export_type=data_type,
        file_path=f"/media/exports/{filename}",
        exported_at=datetime.now(),
        user=str(request.user)
    )

    return JsonResponse({"success": True, "file": f"/media/exports/{filename}"})

@login_required
@role_required(Role.ADMIN)
def grant_export_access(request):
    """Autorise un manager à télécharger les exports PDF/CSV sans limite de temps et notifie."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    user_id = request.POST.get("user_id")
    User = get_user_model()
    try:
        target = User.objects.get(id=user_id, is_active=True, role=Role.MANAGER)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "Utilisateur introuvable."}, status=404)

    if getattr(target, "can_export", False):
        return JsonResponse({"success": True, "message": "L'utilisateur est déjà autorisé."})

    target.can_export = True
    target.save(update_fields=["can_export"])

    Notification.create_notification(
        user=target,
        title="✅ Accès export accordé",
        message="Vous avez maintenant accès aux exports PDF et CSV. Vous pouvez télécharger les rapports depuis la page Exports.",
        notification_type="export",
        priority="high",
        action_url="/dashboard/exports/",
        action_label="Voir les exports",
        icon="bi-unlock-fill"
    )

    # Notification pour l'admin qui a accordé l'accès
    if request.user.is_authenticated:
        Notification.create_notification(
            user=request.user,
            title="Accès export accordé",
            message=f"Vous avez autorisé {target.first_name} {target.last_name} ({target.email}) à accéder aux exports.",
            notification_type="user",
            priority="low",
            action_url="/dashboard/exports/",
            action_label="Voir les managers",
            icon="bi-check-circle-fill"
        )

    return JsonResponse({"success": True, "message": "Accès export accordé et notification envoyée."})


@login_required
@role_required(Role.ADMIN)
def revoke_export_access(request):
    """Révoque l'accès aux exports d'un manager."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    user_id = request.POST.get("user_id")
    User = get_user_model()
    try:
        target = User.objects.get(id=user_id, is_active=True, role=Role.MANAGER)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "Utilisateur introuvable."}, status=404)

    if not getattr(target, "can_export", False):
        return JsonResponse({"success": True, "message": "L'utilisateur n'a déjà pas accès aux exports."})

    target.can_export = False
    target.save(update_fields=["can_export"])

    # Notification au manager
    Notification.create_notification(
        user=target,
        title="⚠️ Accès export révoqué",
        message="Votre accès aux exports a été révoqué par un administrateur. Vous ne pouvez plus télécharger de rapports.",
        notification_type="warning",
        priority="high",
        action_url="/dashboard/exports/",
        action_label="Voir la page exports",
        icon="bi-lock-fill"
    )

    # Notification pour l'admin qui a révoqué l'accès
    if request.user.is_authenticated:
        Notification.create_notification(
            user=request.user,
            title="Accès export révoqué",
            message=f"Vous avez révoqué l'accès aux exports de {target.first_name} {target.last_name} ({target.email}).",
            notification_type="user",
            priority="low",
            action_url="/dashboard/exports/",
            action_label="Voir les managers",
            icon="bi-lock-fill"
        )

    return JsonResponse({"success": True, "message": "Accès export révoqué et notification envoyée."})

@login_required
def export_dashboard_pdf(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès réservé aux administrateurs ou utilisateurs autorisés.", status=403)
    """Exporte le dashboard principal en PDF"""
    try:
        pdf_buffer = generate_dashboard_pdf()

        filename = f"dashboard_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Enregistrer dans l'historique
        export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)

        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.read())

        ExportHistory.objects.create(
            export_type="dashboard_pdf",
            file_path=f"/media/exports/{filename}",
            exported_at=datetime.now(),
            user=str(request.user) if request.user.is_authenticated else "Système"
        )

        #  Créer une notification pour l'utilisateur
        if request.user.is_authenticated:
            Notification.create_notification(
                user=request.user,
                title="Export PDF généré avec succès",
                message=f"Votre rapport Dashboard général ({filename}) est prêt à être téléchargé.",
                notification_type='export',
                priority='normal',
                action_url='/dashboard/exports/',
                action_label='Voir les exports',
                icon='bi-file-earmark-pdf-fill'
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pdf_buffer.seek(0)
        response.write(pdf_buffer.read())

        return response

    except Exception as e:
        return HttpResponse(f"Erreur lors de la génération du PDF: {str(e)}", status=500)

@login_required
def export_sessions_pdf(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès réservé aux administrateurs ou utilisateurs autorisés.", status=403)
    """Exporte les sessions en PDF"""
    try:
        pdf_buffer = generate_sessions_pdf()

        filename = f"sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Enregistrer dans l'historique
        export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)

        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.read())

        ExportHistory.objects.create(
            export_type="sessions_pdf",
            file_path=f"/media/exports/{filename}",
            exported_at=datetime.now(),
            user=str(request.user) if request.user.is_authenticated else "Système"
        )

        # Notification
        if request.user.is_authenticated:
            Notification.create_notification(
                user=request.user,
                title="Rapport Sessions exporté",
                message=f"Votre rapport d'analyse des sessions ({filename}) est disponible.",
                notification_type='export',
                priority='normal',
                action_url='/dashboard/exports/',
                action_label='Télécharger',
                icon='bi-people-fill'
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pdf_buffer.seek(0)
        response.write(pdf_buffer.read())

        return response

    except Exception as e:
        return HttpResponse(f"Erreur lors de la génération du PDF: {str(e)}", status=500)

@login_required
def export_chatbot_pdf(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès réservé aux administrateurs ou utilisateurs autorisés.", status=403)
    """Exporte les données chatbot en PDF"""
    try:
        pdf_buffer = generate_chatbot_pdf()

        filename = f"chatbot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Enregistrer dans l'historique
        export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)

        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.read())

        ExportHistory.objects.create(
            export_type="chatbot_pdf",
            file_path=f"/media/exports/{filename}",
            exported_at=datetime.now(),
            user=str(request.user) if request.user.is_authenticated else "Système"
        )

        # Notification
        if request.user.is_authenticated:
            Notification.create_notification(
                user=request.user,
                title="Rapport Chatbot exporté",
                message=f"Votre rapport d'analyse du chatbot ({filename}) est prêt.",
                notification_type='export',
                priority='normal',
                action_url='/dashboard/exports/',
                action_label='Télécharger',
                icon='bi-robot'
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pdf_buffer.seek(0)
        response.write(pdf_buffer.read())

        return response

    except Exception as e:
        return HttpResponse(f"Erreur lors de la génération du PDF: {str(e)}", status=500)

@login_required
def export_products_pdf(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès réservé aux administrateurs ou utilisateurs autorisés.", status=403)
    """Exporte les données produits en PDF"""
    try:
        pdf_buffer = generate_products_pdf()

        filename = f"produits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Enregistrer dans l'historique
        export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)

        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.read())

        ExportHistory.objects.create(
            export_type="products_pdf",
            file_path=f"/media/exports/{filename}",
            exported_at=datetime.now(),
            user=str(request.user) if request.user.is_authenticated else "Système"
        )

        # Notification
        if request.user.is_authenticated:
            Notification.create_notification(
                user=request.user,
                title="Rapport Produits exporté",
                message=f"Votre rapport d'analyse des produits ({filename}) est disponible.",
                notification_type='export',
                priority='normal',
                action_url='/dashboard/exports/',
                action_label='Télécharger',
                icon='bi-box-seam-fill'
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pdf_buffer.seek(0)
        response.write(pdf_buffer.read())

        return response

    except Exception as e:
        return HttpResponse(f"Erreur lors de la génération du PDF: {str(e)}", status=500)

@login_required
def export_clicks_pdf(request):
    if getattr(request.user, "role", None) != Role.ADMIN and not getattr(request.user, "can_export", False):
        return HttpResponse("Accès réservé aux administrateurs ou utilisateurs autorisés.", status=403)
    """Exporte les données de consultations en PDF"""
    try:
        pdf_buffer = generate_clicks_pdf()

        filename = f"consultations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Enregistrer dans l'historique
        export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)

        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.read())

        ExportHistory.objects.create(
            export_type="clicks_pdf",
            file_path=f"/media/exports/{filename}",
            exported_at=datetime.now(),
            user=str(request.user) if request.user.is_authenticated else "Système"
        )

        #  Notification
        if request.user.is_authenticated:
            Notification.create_notification(
                user=request.user,
                title="Rapport Consultations exporté",
                message=f"Votre rapport d'analyse des consultations ({filename}) est prêt.",
                notification_type='export',
                priority='normal',
                action_url='/dashboard/exports/',
                action_label='Télécharger',
                icon='bi-mouse-fill'
            )

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pdf_buffer.seek(0)
        response.write(pdf_buffer.read())

        return response

    except Exception as e:
        return HttpResponse(f"Erreur lors de la génération du PDF: {str(e)}", status=500)
