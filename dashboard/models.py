from django.db import models
from django.utils import timezone


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
    """
    Fiche produit complète utilisée pour les recommandations chatbot.
    """
    product_id = models.CharField(max_length=100, unique=True, verbose_name="ID produit (référence interne)")
    name = models.CharField(max_length=255, verbose_name="Nom du produit")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    category = models.CharField(max_length=100, blank=True, null=True, verbose_name="Catégorie")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    available = models.BooleanField(default=True, verbose_name="Disponible")
    image_url = models.URLField(blank=True, null=True, verbose_name="Image (URL)")
    brand = models.CharField(max_length=255, blank=True, null=True, verbose_name="Marque")

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
