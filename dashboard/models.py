from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

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

    def __str__(self):
        return f"Session {self.id} - {self.user_id or 'visiteur'}"


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
        constraints = [
            models.CheckConstraint(check=Q(price__gte=0), name="product_price_gte_0"),
        ]

    def __str__(self):
        return f"{self.name} ({'Disponible' if self.available else 'Indisponible'})"
# ==========================
# CLIC UTILISATEUR
# ==========================
class Click(models.Model):
    """
    Historique des clics utilisateurs (anonymes)
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="clicks")
    product_name = models.CharField(max_length=200, blank=True, null=True)
    page = models.CharField(max_length=200)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Clic sur {self.product_name or self.page}"


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
    location = models.CharField(max_length=150, default="Decathlon Lille Centre")
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
