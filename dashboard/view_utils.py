
from datetime import timedelta, datetime
from django.utils import timezone


def format_duration(td):
    """Return a human-readable duration from a timedelta."""
    if not td:
        return "-"
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def get_period_range(request, prefix=""):
    """
    Parse un filtre de période (today, 7days, 30days, custom) depuis les query params.
    Retourne (period, start_date, end_date).
    """
    period = request.GET.get(f"{prefix}period", "all")
    start_date = end_date = None
    today = timezone.now()

    if period == "today":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7days":
        start_date = today - timedelta(days=7)
    elif period == "30days":
        start_date = today - timedelta(days=30)
    elif period == "custom":
        start_raw = request.GET.get(f"{prefix}start_date")
        end_raw = request.GET.get(f"{prefix}end_date")
        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d") if start_raw else None
        except (TypeError, ValueError):
            start_date = None
        try:
            end_date = datetime.strptime(end_raw, "%Y-%m-%d") if end_raw else None
        except (TypeError, ValueError):
            end_date = None

    return period, start_date, end_date
