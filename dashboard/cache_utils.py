"""
Utilitaires de cache Redis pour optimiser les performances du dashboard.
"""
from django.core.cache import cache
from functools import wraps
import hashlib
import json


def cache_dashboard_kpis(timeout=300):
    """
    Décorateur pour cacher les KPIs du dashboard.
    Timeout par défaut: 5 minutes (300 secondes).

    Usage:
        @cache_dashboard_kpis(timeout=600)
        def get_dashboard_stats():
            return {...}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Créer une clé de cache unique basée sur le nom de la fonction et les arguments
            cache_key = _generate_cache_key(func.__name__, args, kwargs)

            # Essayer de récupérer depuis le cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Sinon, exécuter la fonction et mettre en cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper
    return decorator


def _generate_cache_key(func_name, args, kwargs):
    """
    Génère une clé de cache unique basée sur le nom de fonction et les arguments.
    """
    # Convertir args et kwargs en string JSON pour créer un hash
    args_str = json.dumps(args, sort_keys=True, default=str)
    kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)

    # Créer un hash MD5
    hash_input = f"{func_name}:{args_str}:{kwargs_str}"
    hash_digest = hashlib.md5(hash_input.encode()).hexdigest()

    return f"dashboard_kpi:{func_name}:{hash_digest}"


def invalidate_dashboard_cache():
    """
    Invalide tous les caches du dashboard.
    À appeler après des modifications de données (création session, interaction chatbot, etc.).
    """
    # Pattern matching pour supprimer toutes les clés commençant par "liasec:dashboard_kpi:"
    from django_redis import get_redis_connection
    try:
        conn = get_redis_connection("default")
        pattern = "liasec:dashboard_kpi:*"
        keys = conn.keys(pattern)
        if keys:
            conn.delete(*keys)
            return len(keys)
        return 0
    except Exception as e:
        # Si Redis est down, ne pas crasher
        print(f"[CACHE] Erreur lors de l'invalidation du cache: {e}")
        return 0


def get_cached_value(key, default=None):
    """
    Récupère une valeur depuis le cache avec gestion d'erreur.
    """
    try:
        return cache.get(key, default)
    except Exception as e:
        print(f"[CACHE] Erreur lors de la récupération: {e}")
        return default


def set_cached_value(key, value, timeout=300):
    """
    Définit une valeur dans le cache avec gestion d'erreur.
    """
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as e:
        print(f"[CACHE] Erreur lors de la mise en cache: {e}")
        return False


def cache_key_for_period(base_key, period='7days'):
    """
    Génère une clé de cache spécifique à une période.
    """
    return f"{base_key}:{period}"
