"""
Template tags personnalisés pour le dashboard.
"""
from django import template

register = template.Library()


@register.filter
def trend_icon(trend_dict):
    """
    Retourne l'icône appropriée pour une tendance.

    Usage: {{ kpi.trend|trend_icon }}
    """
    if not trend_dict:
        return ''

    direction = trend_dict.get('direction', 'stable')

    if direction == 'up':
        return '<i class="bi bi-arrow-up-right text-success fs-5"></i>'
    elif direction == 'down':
        return '<i class="bi bi-arrow-down-right text-danger fs-5"></i>'
    else:
        return '<i class="bi bi-dash text-muted fs-5"></i>'


@register.filter
def trend_class(trend_dict):
    """
    Retourne la classe CSS appropriée pour une tendance.

    Usage: <span class="{{ kpi.trend|trend_class }}">
    """
    if not trend_dict:
        return 'text-muted'

    direction = trend_dict.get('direction', 'stable')

    if direction == 'up':
        return 'text-success'
    elif direction == 'down':
        return 'text-danger'
    else:
        return 'text-muted'


@register.filter
def trend_badge(trend_dict):
    """
    Retourne un badge complet avec icône et texte.

    Usage: {{ kpi.trend|trend_badge|safe }}
    """
    if not trend_dict:
        return ''

    direction = trend_dict.get('direction', 'stable')
    formatted = trend_dict.get('formatted', '0%')

    if direction == 'up':
        icon = '<i class="bi bi-arrow-up-right me-1"></i>'
        badge_class = 'badge bg-success bg-opacity-10 text-success'
    elif direction == 'down':
        icon = '<i class="bi bi-arrow-down-right me-1"></i>'
        badge_class = 'badge bg-danger bg-opacity-10 text-danger'
    else:
        icon = '<i class="bi bi-dash me-1"></i>'
        badge_class = 'badge bg-secondary bg-opacity-10 text-secondary'

    return f'<span class="{badge_class}">{icon}{formatted}</span>'


@register.inclusion_tag('dashboard/includes/_kpi_card.html')
def kpi_card(label, value, icon, color='primary', trend=None, description=None, tooltip=None):
    """
    Affiche une carte KPI complète avec tendance.

    Usage:
        {% kpi_card label="Sessions" value=1234 icon="bi-people" color="primary" trend=sessions_trend %}
    """
    return {
        'label': label,
        'value': value,
        'icon': icon,
        'color': color,
        'trend': trend,
        'description': description,
        'tooltip': tooltip
    }


@register.simple_tag
def trend_arrow(trend_dict):
    """
    Retourne une flèche Unicode simple.

    Usage: {% trend_arrow kpi.trend %}
    """
    if not trend_dict:
        return '→'

    direction = trend_dict.get('direction', 'stable')

    if direction == 'up':
        return '↗'
    elif direction == 'down':
        return '↘'
    else:
        return '→'


@register.filter
def percentage(value, decimals=1):
    """
    Formate un nombre en pourcentage.

    Usage: {{ 0.1234|percentage }} → 12.3%
    """
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return "0%"


@register.filter
def delta_format(current, previous):
    """
    Calcule et formate le delta entre deux valeurs.

    Usage: {{ current_value|delta_format:previous_value }}
    """
    try:
        current = float(current)
        previous = float(previous)

        if previous == 0:
            if current == 0:
                return "+0"
            else:
                return f"+{current:,.0f}"

        delta = current - previous
        sign = '+' if delta >= 0 else ''
        return f"{sign}{delta:,.0f}"
    except (ValueError, TypeError):
        return "+0"
