
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


@login_required
def get_notifications_api(request):
    notifications = Notification.objects.filter(
        user=request.user,
        is_archived=False
    )[:10]
    
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'priority': n.priority,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'action_url': n.action_url,
        'action_label': n.action_label,
        'icon': n.icon or get_notification_icon(n.notification_type),
    } for n in notifications]
    
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        is_archived=False
    ).count()
    
    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count,
        'success': True
    })

@login_required
@require_POST
@csrf_protect
def mark_notification_read(request, notification_id):
    """Marquer une notification comme lue."""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return JsonResponse({'success': True, 'message': 'Notification marqu�e comme lue'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
@csrf_protect
def mark_all_notifications_read(request):
    """Marquer toutes les notifications comme lues."""
    try:
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return JsonResponse({'success': True, 'message': 'Toutes les notifications ont �t� marqu�es comme lues'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
@csrf_protect
def delete_notification(request, notification_id):
    """Supprimer (archiver) une notification."""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.archive()
        return JsonResponse({'success': True, 'message': 'Notification supprim�e'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def notifications_page(request):
    """Page de gestion des notifications."""
    # Filtres
    filter_type = request.GET.get('type', '')
    filter_status = request.GET.get('status', '')
    
    notifications = Notification.objects.filter(user=request.user, is_archived=False)
    
    if filter_type:
        notifications = notifications.filter(notification_type=filter_type)
    
    if filter_status == 'read':
        notifications = notifications.filter(is_read=True)
    elif filter_status == 'unread':
        notifications = notifications.filter(is_read=False)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Stats
    total_notifications = Notification.objects.filter(user=request.user, is_archived=False).count()
    unread_count = Notification.objects.filter(user=request.user, is_read=False, is_archived=False).count()
    read_count = total_notifications - unread_count
    
    context = {
        'page_obj': page_obj,
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'read_count': read_count,
        'filter_type': filter_type,
        'filter_status': filter_status,
    }
    
    return render(request, 'dashboard/notifications.html', context)

def get_notification_icon(notification_type):
    icons = {
        'info': 'bi-info-circle-fill',
        'success': 'bi-check-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'error': 'bi-x-circle-fill',
        'system': 'bi-gear-fill',
        'export': 'bi-download',
        'analytics': 'bi-graph-up',
        'user': 'bi-person-fill',
    }
    return icons.get(notification_type, 'bi-bell-fill')
