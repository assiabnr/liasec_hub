"""
Utilitaires d'analytics pour calculer les tendances et comparaisons.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q


def calculate_trend(current_value, previous_value):
    """
    Calcule le pourcentage de changement entre deux valeurs.

    Returns:
        dict: {
            'value': float,        # Pourcentage de changement
            'direction': str,      # 'up', 'down', ou 'stable'
            'is_positive': bool,   # True si c'est une augmentation
            'formatted': str       # Ex: "+12.5%"
        }
    """
    if previous_value == 0:
        if current_value == 0:
            return {
                'value': 0,
                'direction': 'stable',
                'is_positive': None,
                'formatted': '0%'
            }
        else:
            return {
                'value': 100,
                'direction': 'up',
                'is_positive': True,
                'formatted': '+100%'
            }

    percentage = ((current_value - previous_value) / previous_value) * 100

    # Déterminer la direction
    if percentage > 0.5:
        direction = 'up'
        is_positive = True
    elif percentage < -0.5:
        direction = 'down'
        is_positive = False
    else:
        direction = 'stable'
        is_positive = None

    # Formatter
    if direction == 'stable':
        formatted = '0%'
    else:
        sign = '+' if percentage > 0 else ''
        formatted = f"{sign}{percentage:.1f}%"

    return {
        'value': percentage,
        'direction': direction,
        'is_positive': is_positive,
        'formatted': formatted
    }


def get_period_comparison(queryset, date_field='created_at', periods=7):
    """
    Compare deux périodes identiques (cette période vs période précédente).

    Args:
        queryset: QuerySet Django
        date_field: Nom du champ de date
        periods: Nombre de jours pour chaque période (défaut: 7 jours)

    Returns:
        dict: {
            'current_count': int,
            'previous_count': int,
            'trend': dict (retour de calculate_trend)
        }
    """
    now = timezone.now()
    period_start = now - timedelta(days=periods)
    previous_period_start = period_start - timedelta(days=periods)

    # Période actuelle
    current_filter = {f'{date_field}__gte': period_start}
    current_count = queryset.filter(**current_filter).count()

    # Période précédente
    previous_filter = {
        f'{date_field}__gte': previous_period_start,
        f'{date_field}__lt': period_start
    }
    previous_count = queryset.filter(**previous_filter).count()

    return {
        'current_count': current_count,
        'previous_count': previous_count,
        'trend': calculate_trend(current_count, previous_count)
    }


def get_avg_comparison(queryset, value_field, date_field='created_at', periods=7):
    """
    Compare la moyenne d'un champ entre deux périodes.

    Returns:
        dict: {
            'current_avg': float,
            'previous_avg': float,
            'trend': dict
        }
    """
    now = timezone.now()
    period_start = now - timedelta(days=periods)
    previous_period_start = period_start - timedelta(days=periods)

    # Moyenne période actuelle
    current_filter = {f'{date_field}__gte': period_start}
    current_result = queryset.filter(**current_filter).aggregate(avg=Avg(value_field))
    current_avg = current_result['avg'] or 0

    # Moyenne période précédente
    previous_filter = {
        f'{date_field}__gte': previous_period_start,
        f'{date_field}__lt': period_start
    }
    previous_result = queryset.filter(**previous_filter).aggregate(avg=Avg(value_field))
    previous_avg = previous_result['avg'] or 0

    return {
        'current_avg': round(current_avg, 2),
        'previous_avg': round(previous_avg, 2),
        'trend': calculate_trend(current_avg, previous_avg)
    }


def get_kpi_with_trend(current_value, queryset, date_field='created_at', periods=7):
    """
    Enrichit un KPI avec sa tendance.

    Usage:
        sessions_kpi = get_kpi_with_trend(
            current_value=Session.objects.count(),
            queryset=Session.objects.all(),
            date_field='start_time',
            periods=7
        )

    Returns:
        dict: {
            'value': int,
            'comparison': dict,
            'trend': dict
        }
    """
    comparison = get_period_comparison(queryset, date_field, periods)

    return {
        'value': current_value,
        'current_period': comparison['current_count'],
        'previous_period': comparison['previous_count'],
        'trend': comparison['trend']
    }


def format_kpi_html(kpi_data, label, icon_class="bi-graph-up", color="primary"):
    """
    Génère le HTML pour un KPI avec tendance.

    Returns:
        str: HTML formaté prêt à insérer dans un template
    """
    trend = kpi_data.get('trend', {})
    direction = trend.get('direction', 'stable')

    # Icône de tendance
    if direction == 'up':
        trend_icon = '<i class="bi bi-arrow-up-right text-success"></i>'
        trend_class = 'text-success'
    elif direction == 'down':
        trend_icon = '<i class="bi bi-arrow-down-right text-danger"></i>'
        trend_class = 'text-danger'
    else:
        trend_icon = '<i class="bi bi-dash text-muted"></i>'
        trend_class = 'text-muted'

    return {
        'label': label,
        'value': kpi_data['value'],
        'trend_icon': trend_icon,
        'trend_class': trend_class,
        'trend_text': trend.get('formatted', '0%'),
        'icon_class': icon_class,
        'color': color
    }
