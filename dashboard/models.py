from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model


class SessionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)


class ActiveSessionManager(models.Manager):
    def get_queryset(self):
        return SessionQuerySet(self.model, using=self._db).filter(is_deleted=False)


class ActiveBySessionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(session__is_deleted=False)

User = get_user_model()


# ==========================
# SESSION UTILISATEUR
# ==========================
class Session(models.Model):
    """
    Session utilisateur anonyme (visiteur unique, device, localisation)
    """
    user_id = models.CharField(max_length=100, blank=True, null=True)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)
    device = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=150, blank=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = ActiveSessionManager()
    all_objects = SessionQuerySet.as_manager()

    def __str__(self):
        return f"Session {self.id} - {self.user_id or 'visiteur'}"

    def soft_delete(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(update_fields=["is_deleted", "deleted_at"])


# ==========================
# PRODUIT (fiche produit complète)
# ==========================

class Product(models.Model):
    product_id = models.CharField(max_length=100, unique=True)                  # ← non-null
    name = models.CharField(max_length=255)                                      # ← non-null
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=150, blank=True, null=True)
    sport = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=255, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)      # ← non-null avec default
    available = models.BooleanField(default=True, db_index=True)
    image_url = models.URLField(blank=True, null=True)
    image_url_alt = models.URLField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["category"]),
        ]


    def __str__(self):
        return f"{self.name} ({'Disponible' if self.available else 'Indisponible'})"
# ==========================
# PRODUITS CONSULTÉS
# ==========================
class ProductView(models.Model):
    """
    Suivi des produits réellement consultés par les utilisateurs.
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="product_views")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True, related_name="views")
    viewed_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Origine du clic (ex: 'carte', 'recherche', 'chatbot', etc.)",
    )
    zone = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Zone du magasin (ex: 'FIT HOMME', 'CHAUSSANT', etc.)",
    )

    objects = ActiveBySessionManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"{self.product.name if self.product else 'Produit inconnu'} ({self.source or 'inconnu'})"


# ==========================
# INTERACTIONS CHATBOT (ANALYTIQUES)
# ==========================
class ChatbotInteraction(models.Model):
    """
    Enregistre chaque interaction utilisateur avec le chatbot
    et inclut des données analytiques sur la compréhension, le succès et la satisfaction.
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="chatbot_interactions")
    question = models.TextField()
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    model_used = models.CharField(max_length=50, default="Mistral")


    # === Nouveaux champs analytiques ===
    intent = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Intention détectée (ex: produit, magasin, livraison...)"
    )
    response_success = models.BooleanField(
        default=True,
        help_text="La réponse du chatbot était-elle correcte / pertinente ?"
    )
    response_time = models.FloatField(
        blank=True,
        null=True,
        help_text="Temps de génération de la réponse (secondes)"
    )
    satisfaction = models.BooleanField(
        blank=True,
        null=True,
        help_text="Satisfaction binaire : Oui (True) / Non (False)"
    )
    sentiment = models.FloatField(
        blank=True,
        null=True,
        help_text="Analyse de sentiment (-1 = négatif, +1 = positif)"
    )
    ask_feedback = models.BooleanField(
        default=False,
        help_text="Indique si un feedback utilisateur doit être demandé pour cette interaction"
    )

    objects = ActiveBySessionManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"Chatbot ({self.model_used}) - {self.intent or 'Sans intent'}"


# ==========================
# RECOMMANDATIONS CHATBOT (LIÉES À DE VRAIS PRODUITS)
# ==========================
class ChatbotRecommendation(models.Model):
    """
    Produit recommandé par le chatbot dans le cadre d'une interaction.
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="chatbot_recommendations")
    interaction = models.ForeignKey(ChatbotInteraction, on_delete=models.CASCADE, related_name="recommendations")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="chatbot_recommendations")
    recommended_at = models.DateTimeField(default=timezone.now)

    # === Nouveau champ : suivi de clics ===
    clicked = models.BooleanField(default=False, help_text="L'utilisateur a-t-il cliqué sur cette recommandation ?")

    objects = ActiveBySessionManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"Reco: {self.product.name} (session {self.session.id})"


# ==========================
# HISTORIQUE D’EXPORTS
# ==========================
class ExportHistory(models.Model):
    """
    Historique des fichiers exportés depuis le dashboard.
    """
    export_type = models.CharField(max_length=50)
    exported_at = models.DateTimeField(default=timezone.now)
    file_path = models.CharField(max_length=255)
    user = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Export {self.export_type} du {self.exported_at.strftime('%d/%m/%Y %H:%M')}"


# ==========================
# PARAMÈTRES GLOBAUX DU DASHBOARD
# ==========================
class Settings(models.Model):
    """
    Configuration générale de la borne / dashboard.
    """
    name = models.CharField(max_length=100, default="Borne tactile v2.1")
    location = models.CharField(max_length=150, default="Decathlon Le Mans")
    code = models.CharField(max_length=50, default="BNL-021")

    # Options de tracking
    track_sessions = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    track_chatbot = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


# ==========================
# NOTIFICATIONS SYSTÈME
# ==========================
class Notification(models.Model):
    """
    Système de notifications pour les utilisateurs du dashboard.
    """

    # Types de notifications
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('system', 'Système'),
        ('export', 'Export'),
        ('analytics', 'Analytiques'),
        ('user', 'Utilisateur'),
    ]

    # Priorités
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('normal', 'Normale'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')

    # Statut
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    # Métadonnées
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(blank=True, null=True)

    # Action liée (optionnel)
    action_url = models.CharField(max_length=255, blank=True, null=True, help_text="URL vers laquelle rediriger")
    action_label = models.CharField(max_length=100, blank=True, null=True, help_text="Libellé du bouton d'action")

    # Icône personnalisée (optionnel)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Classe d'icône Bootstrap Icons")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    def mark_as_read(self):
        """Marquer la notification comme lue."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    def mark_as_unread(self):
        """Marquer la notification comme non lue."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()

    def archive(self):
        """Archiver la notification."""
        self.is_archived = True
        self.save()

    @staticmethod
    def create_notification(user, title, message, notification_type='info', priority='normal', action_url=None, action_label=None, icon=None):
        """
        Méthode helper pour créer une notification.
        """
        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            action_url=action_url,
            action_label=action_label,
            icon=icon
        )


# ==========================
# DEMANDES D'ACCÈS EXPORT
# ==========================
class ExportRequest(models.Model):
    """
    Système de demandes d'accès aux exports pour les managers.
    Les managers peuvent demander l'accès, les admins peuvent approuver/refuser.
    """

    # Statuts possibles
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('APPROVED', 'Approuvée'),
        ('REJECTED', 'Refusée'),
    ]

    # Demandeur
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='export_requests',
        help_text="Manager qui demande l'accès"
    )

    # Statut de la demande
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    # Justification de la demande
    reason = models.TextField(
        help_text="Justification fournie par le manager"
    )

    # Dates
    requested_at = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création de la demande"
    )
    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date de traitement par l'admin"
    )

    # Réviseur (admin qui traite la demande)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_export_requests',
        help_text="Admin qui a traité la demande"
    )

    # Message de réponse de l'admin
    response_message = models.TextField(
        blank=True,
        null=True,
        help_text="Message optionnel de l'admin (surtout en cas de refus)"
    )

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['status', 'requested_at']),
        ]

    def __str__(self):
        return f"Demande d'export de {self.requester.email} - {self.get_status_display()}"

    def approve(self, admin_user, message=None):
        """
        Approuve la demande et active l'accès export pour le manager.
        """
        self.status = 'APPROVED'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.response_message = message or "Votre demande d'accès aux exports a été approuvée."
        self.save()

        # Activer l'accès export pour le manager
        self.requester.can_export = True
        self.requester.save(update_fields=['can_export'])

        # Créer une notification pour le manager
        Notification.create_notification(
            user=self.requester,
            title="✅ Accès export approuvé",
            message=self.response_message,
            notification_type='success',
            priority='high',
            action_url='/dashboard/exports/',
            action_label='Voir les exports',
            icon='bi-check-circle-fill'
        )

    def reject(self, admin_user, message=None):
        """
        Refuse la demande.
        """
        self.status = 'REJECTED'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.response_message = message or "Votre demande d'accès aux exports a été refusée."
        self.save()

        # Créer une notification pour le manager
        Notification.create_notification(
            user=self.requester,
            title="❌ Demande d'export refusée",
            message=self.response_message,
            notification_type='warning',
            priority='normal',
            action_url='/dashboard/exports/',
            action_label='Voir les détails',
            icon='bi-x-circle-fill'
        )
