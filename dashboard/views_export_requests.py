"""
Vues API pour gérer les demandes d'accès aux exports.
"""
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import get_object_or_404

from accounts.decorators import role_required
from accounts.models import Role
from dashboard.models import ExportRequest, Notification


@login_required
@csrf_protect
@require_POST
def create_export_request(request):
    """
    Permet à un manager de créer une demande d'accès export.
    POST /dashboard/api/export-requests/create/
    Body: {"reason": "Je souhaite accéder aux exports pour..."}
    """
    # Vérifier que l'utilisateur est un manager
    if request.user.role != Role.MANAGER:
        return JsonResponse(
            {"success": False, "error": "Seuls les managers peuvent faire des demandes d'export."},
            status=403
        )

    # Vérifier qu'il n'a pas déjà l'accès
    if request.user.can_export:
        return JsonResponse(
            {"success": False, "error": "Vous avez déjà accès aux exports."},
            status=400
        )

    # Vérifier qu'il n'y a pas déjà une demande en attente
    existing_pending = ExportRequest.objects.filter(
        requester=request.user,
        status='PENDING'
    ).first()

    if existing_pending:
        return JsonResponse(
            {"success": False, "error": "Vous avez déjà une demande en attente."},
            status=400
        )

    # Récupérer la raison
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Données JSON invalides."}, status=400)

    if not reason:
        return JsonResponse(
            {"success": False, "error": "Veuillez fournir une justification."},
            status=400
        )

    if len(reason) < 20:
        return JsonResponse(
            {"success": False, "error": "La justification doit contenir au moins 20 caractères."},
            status=400
        )

    # Créer la demande
    export_request = ExportRequest.objects.create(
        requester=request.user,
        reason=reason
    )

    # Notifier tous les admins
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admins = User.objects.filter(role=Role.ADMIN, is_active=True)

    for admin in admins:
        Notification.create_notification(
            user=admin,
            title="📩 Nouvelle demande d'export",
            message=f"{request.user.first_name} {request.user.last_name} ({request.user.email}) a demandé l'accès aux exports. Raison : {reason[:100]}...",
            notification_type='user',
            priority='normal',
            action_url='/dashboard/exports/',
            action_label='Voir la demande',
            icon='bi-envelope-fill'
        )

    return JsonResponse({
        "success": True,
        "message": "Votre demande a été envoyée aux administrateurs.",
        "request_id": export_request.id
    })


@login_required
@role_required(Role.ADMIN)
def list_export_requests(request):
    """
    Liste toutes les demandes d'export (admin uniquement).
    GET /dashboard/api/export-requests/
    """
    status_filter = request.GET.get('status', 'all')

    queryset = ExportRequest.objects.select_related('requester', 'reviewed_by')

    if status_filter != 'all':
        queryset = queryset.filter(status=status_filter.upper())

    requests_data = []
    for req in queryset[:50]:  # Limiter à 50
        requests_data.append({
            'id': req.id,
            'requester': {
                'id': req.requester.id,
                'email': req.requester.email,
                'first_name': req.requester.first_name,
                'last_name': req.requester.last_name,
            },
            'status': req.status,
            'status_display': req.get_status_display(),
            'reason': req.reason,
            'requested_at': req.requested_at.strftime('%d/%m/%Y à %H:%M'),
            'reviewed_at': req.reviewed_at.strftime('%d/%m/%Y à %H:%M') if req.reviewed_at else None,
            'reviewed_by': {
                'email': req.reviewed_by.email,
                'name': f"{req.reviewed_by.first_name} {req.reviewed_by.last_name}"
            } if req.reviewed_by else None,
            'response_message': req.response_message,
        })

    return JsonResponse({
        'success': True,
        'requests': requests_data,
        'count': len(requests_data)
    })


@login_required
@role_required(Role.ADMIN)
@csrf_protect
@require_POST
def approve_export_request(request, request_id):
    """
    Approuve une demande d'export.
    POST /dashboard/api/export-requests/<id>/approve/
    Body: {"message": "Message optionnel"}
    """
    export_request = get_object_or_404(ExportRequest, id=request_id)

    if export_request.status != 'PENDING':
        return JsonResponse(
            {"success": False, "error": "Cette demande a déjà été traitée."},
            status=400
        )

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
    except json.JSONDecodeError:
        message = ""

    export_request.approve(request.user, message or None)

    return JsonResponse({
        "success": True,
        "message": f"Demande de {export_request.requester.email} approuvée."
    })


@login_required
@role_required(Role.ADMIN)
@csrf_protect
@require_POST
def reject_export_request(request, request_id):
    """
    Refuse une demande d'export.
    POST /dashboard/api/export-requests/<id>/reject/
    Body: {"message": "Raison du refus"}
    """
    export_request = get_object_or_404(ExportRequest, id=request_id)

    if export_request.status != 'PENDING':
        return JsonResponse(
            {"success": False, "error": "Cette demande a déjà été traitée."},
            status=400
        )

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
    except json.JSONDecodeError:
        message = ""

    if not message:
        message = "Votre demande d'accès aux exports a été refusée."

    export_request.reject(request.user, message)

    return JsonResponse({
        "success": True,
        "message": f"Demande de {export_request.requester.email} refusée."
    })


@login_required
def get_my_export_requests(request):
    """
    Récupère les demandes d'export de l'utilisateur connecté (manager).
    GET /dashboard/api/export-requests/my/
    """
    requests = ExportRequest.objects.filter(requester=request.user).select_related('reviewed_by')

    requests_data = []
    for req in requests:
        requests_data.append({
            'id': req.id,
            'status': req.status,
            'status_display': req.get_status_display(),
            'reason': req.reason,
            'requested_at': req.requested_at.strftime('%d/%m/%Y à %H:%M'),
            'reviewed_at': req.reviewed_at.strftime('%d/%m/%Y à %H:%M') if req.reviewed_at else None,
            'reviewed_by': req.reviewed_by.email if req.reviewed_by else None,
            'response_message': req.response_message,
        })

    return JsonResponse({
        'success': True,
        'requests': requests_data,
        'count': len(requests_data)
    })
