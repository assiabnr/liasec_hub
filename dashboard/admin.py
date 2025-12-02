from django.contrib import admin
from .models import (
    Session,
    Product,
    ProductView,
    ChatbotInteraction,
    ChatbotRecommendation,
    ExportHistory,
    Settings,
    Notification,
    ExportRequest,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'priority', 'is_read', 'created_at')
    list_filter = ('notification_type', 'priority', 'is_read', 'is_archived', 'created_at')
    search_fields = ('title', 'message', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'read_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'title', 'message', 'notification_type', 'priority')
        }),
        ('Statut', {
            'fields': ('is_read', 'is_archived', 'read_at')
        }),
        ('Action (optionnel)', {
            'fields': ('action_url', 'action_label', 'icon'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at',)
        }),
    )

    actions = ['mark_as_read', 'mark_as_unread', 'archive_notifications']

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notifications marquées comme lues.")
    mark_as_read.short_description = "Marquer comme lues"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None)
        self.message_user(request, f"{queryset.count()} notifications marquées comme non lues.")
    mark_as_unread.short_description = "Marquer comme non lues"

    def archive_notifications(self, request, queryset):
        queryset.update(is_archived=True)
        self.message_user(request, f"{queryset.count()} notifications archivées.")
    archive_notifications.short_description = "Archiver les notifications"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'available')
    list_filter = ('available', 'category', 'brand', 'sport')
    search_fields = ('name', 'brand', 'category', 'product_id')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'start_time', 'duration', 'device')
    list_filter = ('start_time', 'device', 'is_deleted')
    search_fields = ('user_id',)

    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        for session in queryset:
            session.soft_delete()


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location', 'track_sessions', 'track_clicks', 'track_chatbot')


@admin.register(ExportRequest)
class ExportRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'status', 'requested_at', 'reviewed_by', 'reviewed_at')
    list_filter = ('status', 'requested_at', 'reviewed_at')
    search_fields = ('requester__email', 'requester__first_name', 'requester__last_name', 'reason', 'response_message')
    readonly_fields = ('requested_at', 'reviewed_at')
    ordering = ('-requested_at',)

    fieldsets = (
        ('Demandeur', {
            'fields': ('requester', 'reason', 'requested_at')
        }),
        ('Traitement', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'response_message')
        }),
    )

    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        count = 0
        for export_request in queryset.filter(status='PENDING'):
            export_request.approve(request.user, "Demande approuvée par l'administrateur.")
            count += 1
        self.message_user(request, f"{count} demande(s) approuvée(s).")
    approve_requests.short_description = "Approuver les demandes sélectionnées"

    def reject_requests(self, request, queryset):
        count = 0
        for export_request in queryset.filter(status='PENDING'):
            export_request.reject(request.user, "Demande refusée par l'administrateur.")
            count += 1
        self.message_user(request, f"{count} demande(s) refusée(s).")
    reject_requests.short_description = "Refuser les demandes sélectionnées"
