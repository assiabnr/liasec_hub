
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


def settings_view(request):
    settings_obj, _ = Settings.objects.get_or_create(id=1)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_profile":
            # Mise à jour du profil utilisateur
            user = request.user
            user.first_name = request.POST.get("first_name", "").strip()
            user.last_name = request.POST.get("last_name", "").strip()
            user.email = request.POST.get("email", "").strip()
            user.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")

            # Créer une notification pour l'utilisateur
            if request.user.is_authenticated:
                Notification.create_notification(
                    user=request.user,
                    title="Profil mis à jour",
                    message="Vos informations personnelles ont été mises à jour avec succès.",
                    notification_type='success',
                    priority='low',
                    action_url='/dashboard/settings/',
                    action_label='Voir les paramètres',
                    icon='bi-person-check-fill'
            )

            return redirect("settings")

        elif action == "save":
            if getattr(request.user, "role", None) != Role.ADMIN:
                messages.error(request, "Seuls les administrateurs peuvent modifier les paramètres de la borne.")
                return redirect("settings")
            settings_obj.name = request.POST.get("name", settings_obj.name)
            settings_obj.location = request.POST.get("location", settings_obj.location)
            settings_obj.code = request.POST.get("code", settings_obj.code)
            settings_obj.track_sessions = request.POST.get("track_sessions") == "on"
            settings_obj.track_clicks = request.POST.get("track_clicks") == "on"
            settings_obj.track_chatbot = request.POST.get("track_chatbot") == "on"
            settings_obj.save()
            messages.success(request, "Paramètres sauvegardés avec succès.")

            # Créer une notification pour l'utilisateur
            if request.user.is_authenticated:
                Notification.create_notification(
                    user=request.user,
                    title="Paramètres mis à jour",
                    message="Vos paramètres de la borne ont été sauvegardés avec succès.",
                    notification_type='success',
                    priority='low',
                    action_url='/dashboard/settings/',
                    action_label='Voir les paramètres',
                    icon='bi-check-circle-fill'
            )

            return redirect("settings")

        elif action == "reset":
            if getattr(request.user, "role", None) != Role.ADMIN:
                messages.error(request, "Seuls les administrateurs peuvent réinitialiser les données.")
                return redirect("settings")
            Session.all_objects.all().delete()

            ChatbotInteraction.all_objects.all().delete()
            ProductView.all_objects.all().delete()
            ChatbotRecommendation.all_objects.all().delete()
            messages.warning(request, "Toutes les données ont été réinitialisées.")

            # Créer une notification d'avertissement pour l'utilisateur
            if request.user.is_authenticated:
                Notification.create_notification(
                    user=request.user,
                    title="Données réinitialisées",
                    message="Toutes les données de sessions, clics, interactions chatbot et vues produits ont été supprimées.",
                    notification_type='warning',
                    priority='high',
                    action_url='/dashboard/dashboard/',
                    action_label='Voir le dashboard',
                    icon='bi-exclamation-triangle-fill'
                )

            return redirect("settings")

    return render(request, "dashboard/settings.html", {"settings": settings_obj})

@login_required
@role_required(Role.ADMIN)
def reset_data_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée."}, status=405)

    Session.all_objects.all().delete()

    ChatbotInteraction.all_objects.all().delete()
    ProductView.all_objects.all().delete()
    ChatbotRecommendation.all_objects.all().delete()
    ExportHistory.objects.all().delete()

    # Créer une notification d'avertissement pour l'utilisateur
    Notification.create_notification(
        user=request.user,
        title="Réinitialisation complète effectuée",
        message="Toutes les données incluant l'historique des exports ont été supprimées.",
        notification_type='warning',
        priority='high',
        action_url='/dashboard/dashboard/',
        action_label='Voir le dashboard',
        icon='bi-exclamation-triangle-fill'
    )

    return JsonResponse({"success": True, "message": "Toutes les données ont été réinitialisées."})
