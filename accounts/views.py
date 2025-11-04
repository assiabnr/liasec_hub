import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate, login, logout, get_user_model
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.password_validation import validate_password, ValidationError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.models import Role


# =====================================================
# === Helpers généraux
# =====================================================

def _json_payload(request):
    """Parse le corps JSON d’une requête HTTP."""
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def role_required(*allowed_roles):
    """Décorateur pour restreindre l’accès selon le rôle."""
    def _predicate(user):
        return user.is_authenticated and getattr(user, "role", None) in allowed_roles
    return user_passes_test(_predicate, login_url="login")


def is_admin_or_manager(user):
    """Autorise ADMIN et MANAGER."""
    return user.is_authenticated and getattr(user, "role", None) in (Role.ADMIN, Role.MANAGER)


# =====================================================
# === Authentification & gestion des comptes
# =====================================================

def login_view(request):
    """
    Authentification utilisateur.
    Redirige vers dashboard après connexion réussie.
    Si must_change_password=True → page de changement forcé.
    """
    if request.user.is_authenticated:
        return redirect("dashboard_home")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            if getattr(user, "must_change_password", False):
                messages.info(request, "Veuillez définir un nouveau mot de passe avant de continuer.")
                return redirect("force_change_password")
            messages.success(request, f"Bienvenue {user.first_name or user.email} 👋")
            return redirect("dashboard_home")

        messages.error(request, "Email ou mot de passe incorrect.")
    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    """Déconnexion."""
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect("login")


@login_required
def force_change_password(request):
    """
    Première connexion : impose un changement de mot de passe.
    """
    user = request.user
    if not getattr(user, "must_change_password", False):
        return redirect("dashboard_home")

    if request.method == "POST":
        p1 = request.POST.get("password1") or ""
        p2 = request.POST.get("password2") or ""
        if p1 != p2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        else:
            try:
                validate_password(p1, user=user)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
            else:
                user.set_password(p1)
                user.must_change_password = False
                user.save(update_fields=["password", "must_change_password"])
                messages.success(request, "Mot de passe mis à jour avec succès ✅")
                login(request, user)
                return redirect("dashboard_home")

    return render(request, "accounts/reset_password_confirm.html")


def forgot_password(request):
    """
    Envoi d’un lien de réinitialisation par email.
    (ne révèle pas si l’adresse existe ou non)
    """
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        User = get_user_model()

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            messages.success(request, "Si cet email est enregistré, un lien a été envoyé.")
            return redirect("login")

        token_gen = PasswordResetTokenGenerator()
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_gen.make_token(user)
        reset_url = request.build_absolute_uri(reverse("password_reset_confirm", args=[uidb64, token]))

        subject = "Réinitialisation de votre mot de passe"
        ctx = {"user": user, "reset_url": reset_url, "site_name": "LIASEC"}
        html_body = render_to_string("emails/password_reset.html", ctx)

        msg = EmailMessage(
            subject=subject,
            body=html_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[email],
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)

        messages.success(request, "Si cet email est enregistré, un lien de réinitialisation a été envoyé.")
        return redirect("login")

    return render(request, "accounts/forgot_password.html")


def reset_password_confirm(request, uidb64, token):
    """
    Formulaire de définition d’un nouveau mot de passe (depuis le lien email).
    """
    User = get_user_model()
    token_gen = PasswordResetTokenGenerator()

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except Exception:
        user = None

    if user is None or not token_gen.check_token(user, token):
        messages.error(request, "Lien invalide ou expiré.")
        return redirect("login")

    if request.method == "POST":
        p1 = request.POST.get("password1") or ""
        p2 = request.POST.get("password2") or ""
        if len(p1) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        elif p1 != p2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        else:
            user.set_password(p1)
            user.save(update_fields=["password"])
            messages.success(request, "Mot de passe modifié. Vous pouvez vous connecter.")
            return redirect("login")

    return render(request, "accounts/reset_password_confirm.html", {"uidb64": uidb64, "token": token})


# =====================================================
# === API de gestion des utilisateurs (ADMIN uniquement)
# =====================================================

def _user_dict(u):
    """Conversion d’un utilisateur en dict JSON."""
    return {
        "id": u.id,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "role": u.role,
        "is_active": u.is_active,
    }


@require_http_methods(["GET", "POST"])
@csrf_protect
@role_required(Role.ADMIN)
@login_required
def users_list_create(request):
    """
    GET  -> liste des utilisateurs
    POST -> crée un nouvel utilisateur avec mot de passe temporaire
    (envoi automatique d’un email de bienvenue)
    """
    User = get_user_model()

    # === GET ===
    if request.method == "GET":
        users = User.objects.order_by("last_name", "first_name")
        return JsonResponse({"results": [_user_dict(u) for u in users]})

    # === POST ===
    data = request.POST or _json_payload(request)
    email = (data.get("email") or "").strip().lower()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    role = data.get("role") or Role.MANAGER

    if not email:
        return JsonResponse({"error": "L’adresse email est obligatoire."}, status=400)

    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "Un utilisateur avec cet email existe déjà."}, status=400)

    temp_password = get_random_string(12)
    user = User.objects.create(
        username=email.split("@")[0],
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
        must_change_password=True,
    )
    user.set_password(temp_password)
    user.save()

    # Envoi d’email de bienvenue
    login_url = request.build_absolute_uri(reverse("login"))
    ctx = {"user": user, "login_url": login_url, "temp_password": temp_password, "site_name": "LIASEC"}
    html_body = render_to_string("emails/new_user_welcome.html", ctx)
    msg = EmailMessage(
        subject="Votre accès à la plateforme LIASEC",
        body=html_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[email],
    )
    msg.content_subtype = "html"
    msg.send(fail_silently=False)

    return JsonResponse(_user_dict(user), status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
@csrf_protect
@role_required(Role.ADMIN)
@login_required
def user_detail(request, user_id):
    """
    GET    -> détail utilisateur
    PATCH  -> mise à jour infos / reset mot de passe
    DELETE -> suppression utilisateur
    """
    User = get_user_model()
    user = get_object_or_404(User, pk=user_id)

    # === GET ===
    if request.method == "GET":
        return JsonResponse(_user_dict(user))

    # === DELETE ===
    if request.method == "DELETE":
        user.delete()
        return JsonResponse({}, status=204)

    # === PATCH ===
    data = _json_payload(request)
    changed = False

    if "first_name" in data:
        user.first_name = data["first_name"]
        changed = True
    if "last_name" in data:
        user.last_name = data["last_name"]
        changed = True
    if "role" in data:
        user.role = data["role"]
        changed = True

    # Reset mot de passe
    if data.get("reset_password"):
        temp_password = get_random_string(12)
        user.set_password(temp_password)
        user.must_change_password = True
        changed = True

        # Envoi d’email
        login_url = request.build_absolute_uri(reverse("login"))
        ctx = {"user": user, "login_url": login_url, "temp_password": temp_password, "site_name": "LIASEC"}
        html_body = render_to_string("emails/reset_password_admin.html", ctx)
        msg = EmailMessage(
            subject="Réinitialisation de votre mot de passe LIASEC",
            body=html_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[user.email],
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=True)

    if changed:
        user.save()

    return JsonResponse(_user_dict(user))
