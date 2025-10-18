import json
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.conf import settings

from .models import Role
from .decorators import role_required

User = get_user_model()

def _user_dict(u):
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
def users_list_create(request):
    """
    GET -> liste tous les utilisateurs
    POST -> crée un nouvel utilisateur avec mot de passe temporaire
    """
    if request.method == "GET":
        users = User.objects.order_by("last_name", "first_name")
        return JsonResponse({"results": [_user_dict(u) for u in users]})

    data = json.loads(request.body or "{}")
    email = data.get("email", "").strip().lower()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    role = data.get("role") or getattr(Role, "MANAGER", "MANAGER")


    if not email:
        return JsonResponse({"error": "Email requis."}, status=400)
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Cet utilisateur existe déjà."}, status=400)

    temp_password = get_random_string(12)

    user = User.objects.create_user(
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

    # Email de bienvenue
    login_url = request.build_absolute_uri(reverse("login"))
    ctx = {
        "user": user,
        "login_url": login_url,
        "temp_password": temp_password,
        "site_name": "LIASEC",
    }
    html_body = render_to_string("emails/new_user_welcome.html", ctx)

    msg = EmailMessage(
        subject="Votre accès à la plateforme LIASEC",
        body=html_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[email],
    )
    msg.content_subtype = "html"
    try:
        msg.send(fail_silently=False)
    except Exception as e:
        print("Erreur lors de l’envoi d’email :", e)

    return JsonResponse(_user_dict(user), status=201)


@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
@role_required(Role.ADMIN)
def user_detail(request, user_id):
    """
    PATCH -> modifie nom/prénom/role ou reset password
    DELETE -> supprime le compte
    """
    user = get_object_or_404(User, pk=user_id)

    if request.method == "DELETE":
        user.delete()
        return JsonResponse({}, status=204)

    data = json.loads(request.body or "{}")
    changed = False

    if "first_name" in data:
        user.first_name = data["first_name"]; changed = True
    if "last_name" in data:
        user.last_name = data["last_name"]; changed = True
    if "role" in data:
        user.role = data["role"]; changed = True

    if data.get("reset_password"):
        temp_password = get_random_string(12)
        user.set_password(temp_password)
        user.must_change_password = True
        changed = True

        login_url = request.build_absolute_uri(reverse("login"))
        ctx = {"user": user, "login_url": login_url, "temp_password": temp_password, "site_name": "LIASEC"}
        html_body = render_to_string("emails/new_user_welcome.html", ctx)

        msg = EmailMessage(
            subject="Votre mot de passe a été réinitialisé",
            body=html_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[user.email],
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)

    if changed:
        user.save()

    return JsonResponse(_user_dict(user))
