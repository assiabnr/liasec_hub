from django.contrib.auth.decorators import user_passes_test
from .models import Role

def role_required(*allowed_roles):
    """Protège une vue selon le rôle."""
    def _predicate(u):
        return u.is_authenticated and getattr(u, "role", None) in allowed_roles
    return user_passes_test(_predicate, login_url="login")
