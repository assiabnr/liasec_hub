from django.db import models
from django.utils import timezone
from dashboard.models import Product, Session


class ZoneMagasin(models.Model):
    """
    Représente une zone du magasin (ex: FIT HOMME, CHAUSSANT, NATATION, etc.)
    Correspond aux zones (area) de la carte SVG interactive.
    """
    zone_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="ID de la zone",
        help_text="ID de la zone SVG (ex: area12, area18, etc.)"
    )
    nom = models.CharField(
        max_length=200,
        verbose_name="Nom de la zone",
        help_text="Nom descriptif de la zone (ex: FIT HOMME, NATATION)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description"
    )
    couleur = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Couleur de la zone",
        help_text="Code couleur hex pour l'affichage"
    )
    ordre_affichage = models.IntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        help_text="Ordre d'affichage dans les listes"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Zone active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zone du magasin"
        verbose_name_plural = "Zones du magasin"
        ordering = ['ordre_affichage', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.zone_id})"


class CategorieLocalisation(models.Model):
    """
    Catégorie de produits avec sa localisation dans le magasin.
    Lie les sports/catégories aux zones physiques du magasin.
    """
    sport = models.CharField(
        max_length=200,
        verbose_name="Sport/Catégorie",
        help_text="Nom du sport ou de la catégorie (ex: Natation, Running, etc.)",
        db_index=True
    )
    categorie = models.CharField(
        max_length=200,
        verbose_name="Sous-catégorie",
        help_text="Sous-catégorie spécifique (ex: Maillots de bain, Chaussures de running)",
        blank=True,
        null=True
    )
    zone = models.ForeignKey(
        ZoneMagasin,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name="Zone du magasin"
    )
    rayon = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Numéro de rayon",
        help_text="Numéro ou code du rayon spécifique"
    )
    etagere = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Étage/Étagère",
        help_text="Indication de l'étage ou étagère"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes supplémentaires"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Catégorie active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Catégorie localisée"
        verbose_name_plural = "Catégories localisées"
        ordering = ['sport', 'categorie']
        indexes = [
            models.Index(fields=['sport', 'zone']),
        ]

    def __str__(self):
        if self.categorie:
            return f"{self.sport} - {self.categorie} → {self.zone.nom}"
        return f"{self.sport} → {self.zone.nom}"


class LocalisationProduit(models.Model):
    """
    Localisation précise d'un produit spécifique dans le magasin.
    Permet de suivre l'emplacement exact de chaque référence produit.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="localisations",
        verbose_name="Produit"
    )
    zone = models.ForeignKey(
        ZoneMagasin,
        on_delete=models.CASCADE,
        related_name="produits",
        verbose_name="Zone du magasin"
    )
    rayon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Rayon",
        help_text="Code ou numéro du rayon"
    )
    etagere = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Étagère",
        help_text="Niveau d'étagère (ex: A, B, C ou 1, 2, 3)"
    )
    position = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Position",
        help_text="Position précise sur l'étagère"
    )
    quantite_stock = models.IntegerField(
        default=0,
        verbose_name="Quantité en stock",
        help_text="Quantité disponible à cet emplacement"
    )
    derniere_verification = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Dernière vérification",
        help_text="Date de la dernière vérification du stock"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Localisation active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Localisation de produit"
        verbose_name_plural = "Localisations de produits"
        ordering = ['zone', 'rayon', 'etagere']
        unique_together = [['product', 'zone']]

    def __str__(self):
        location = f"{self.zone.nom}"
        if self.rayon:
            location += f" - Rayon {self.rayon}"
        if self.etagere:
            location += f" - Étagère {self.etagere}"
        return f"{self.product.name} → {location}"

    def get_full_location(self):
        """Retourne la localisation complète sous forme de texte"""
        parts = [self.zone.nom]
        if self.rayon:
            parts.append(f"Rayon {self.rayon}")
        if self.etagere:
            parts.append(f"Étagère {self.etagere}")
        if self.position:
            parts.append(f"Position {self.position}")
        return " - ".join(parts)


class DemandeLocalisation(models.Model):
    """
    Stocke les demandes de localisation effectuées via le chatbot.
    Permet de suivre les interactions utilisateurs avec le système de localisation.
    """
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="demandes_localisation",
        verbose_name="Session utilisateur"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="demandes_localisation",
        verbose_name="Produit recherché"
    )
    categorie = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Catégorie recherchée",
        help_text="Catégorie ou sport recherché par l'utilisateur"
    )
    requete = models.TextField(
        verbose_name="Requête utilisateur",
        help_text="Question posée par l'utilisateur"
    )
    zone_trouvee = models.ForeignKey(
        ZoneMagasin,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="demandes",
        verbose_name="Zone trouvée"
    )
    reponse = models.TextField(
        blank=True,
        null=True,
        verbose_name="Réponse fournie"
    )
    success = models.BooleanField(
        default=True,
        verbose_name="Localisation trouvée",
        help_text="Indique si une localisation a été trouvée"
    )
    interaction_chatbot = models.ForeignKey(
        'dashboard.ChatbotInteraction',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="demandes_localisation",
        verbose_name="Interaction chatbot associée"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Demande de localisation"
        verbose_name_plural = "Demandes de localisation"
        ordering = ['-created_at']

    def __str__(self):
        if self.product:
            return f"Localisation de {self.product.name} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
        elif self.categorie:
            return f"Localisation de {self.categorie} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
        return f"Demande du {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class StatistiqueLocalisation(models.Model):
    """
    Statistiques agrégées sur l'utilisation du système de localisation.
    Permet d'analyser les zones les plus recherchées, les parcours clients, etc.
    """
    date = models.DateField(
        default=timezone.now,
        verbose_name="Date"
    )
    zone = models.ForeignKey(
        ZoneMagasin,
        on_delete=models.CASCADE,
        related_name="statistiques",
        verbose_name="Zone"
    )
    nombre_recherches = models.IntegerField(
        default=0,
        verbose_name="Nombre de recherches",
        help_text="Nombre de fois où cette zone a été recherchée"
    )
    nombre_clics = models.IntegerField(
        default=0,
        verbose_name="Nombre de clics",
        help_text="Nombre de clics sur la zone dans la carte"
    )
    nombre_produits_vus = models.IntegerField(
        default=0,
        verbose_name="Produits consultés",
        help_text="Nombre de produits consultés dans cette zone"
    )
    temps_moyen_recherche = models.FloatField(
        blank=True,
        null=True,
        verbose_name="Temps moyen de recherche (secondes)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Statistique de localisation"
        verbose_name_plural = "Statistiques de localisation"
        ordering = ['-date', 'zone']
        unique_together = [['date', 'zone']]

    def __str__(self):
        return f"{self.zone.nom} - {self.date.strftime('%d/%m/%Y')} ({self.nombre_recherches} recherches)"