# dashboard/models.py
from django.db import models
from django.utils import timezone


class Session(models.Model):
    user_id = models.CharField(max_length=100, blank=True, null=True)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)
    device = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"Session {self.id} - {self.user_id or 'visiteur'}"


class Click(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='clicks')
    product_name = models.CharField(max_length=200, blank=True, null=True)
    page = models.CharField(max_length=200)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Clic sur {self.product_name or self.page}"


class ProductView(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='product_views')
    product_name = models.CharField(max_length=200)
    product_id = models.CharField(max_length=100)
    viewed_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Origine du clic (ex: 'carte', 'recherche', 'chatbot', etc.)"
    )
    zone = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Zone du magasin (ex: 'FIT HOMME', 'CHAUSSANT', etc.)"
    )

    def __str__(self):
        return f"{self.product_name} ({self.source or 'inconnu'})"



class ChatbotInteraction(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='chatbot_interactions')
    question = models.TextField()
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    model_used = models.CharField(max_length=50, default="Mistral")

    satisfaction = models.BooleanField(
        blank=True, null=True,
        help_text="L'utilisateur est-il satisfait ? (Oui/Non)"
    )

    def __str__(self):
        return f"Chatbot ({self.model_used}) - {self.question[:40]}..."



class ExportHistory(models.Model):
    export_type = models.CharField(max_length=50)
    exported_at = models.DateTimeField(default=timezone.now)
    file_path = models.CharField(max_length=255)
    user = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Export {self.export_type} du {self.exported_at.strftime('%d/%m/%Y %H:%M')}"


class Settings(models.Model):
    name = models.CharField(max_length=100, default="Borne tactile v2.1")
    location = models.CharField(max_length=150, default="Decathlon Lille Centre")
    code = models.CharField(max_length=50, default="BNL-021")

    # Tracking options
    track_sessions = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    track_chatbot = models.BooleanField(default=True)

    # Date de mise à jour
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"
