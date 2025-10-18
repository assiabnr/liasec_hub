from django.utils import timezone
from datetime import timedelta
import random
from dashboard.models import Session, Click, ProductView, ChatbotInteraction

# Nettoyage complet des anciennes données
ChatbotInteraction.objects.all().delete()
ProductView.objects.all().delete()
Click.objects.all().delete()
Session.objects.all().delete()

# --- Données de référence ---
magasins = [
    "Decathlon Paris La Villette",
    "Decathlon Lyon Part-Dieu",
    "Decathlon Marseille Prado",
    "Decathlon Lille Centre",
    "Decathlon Bordeaux Lac",
    "Decathlon Toulouse Blagnac",
]

devices = [
    "Borne tactile v2.1",
    "Borne tactile v3.0",
    "Kiosque Android",
    "Ecran interactif 32 pouces",
]

zones = [
    "FIT HOMME",
    "FIT FEMME",
    "RANDONNEE",
    "CAMPING",
    "RUNNING",
    "CYCLISME",
]

produits = [
    {"id": "P001", "name": "Chaussures de randonnee MH100 Homme", "categorie": "Randonnee", "zone": "RANDONNEE"},
    {"id": "P002", "name": "Velo tout terrain Rockrider ST530", "categorie": "Cyclisme", "zone": "CYCLISME"},
    {"id": "P003", "name": "Tente de camping MH500 3 personnes", "categorie": "Camping", "zone": "CAMPING"},
    {"id": "P004", "name": "Sac a dos Forclaz 40L Trek", "categorie": "Randonnee", "zone": "RANDONNEE"},
    {"id": "P005", "name": "Montre GPS Garmin Instinct 2", "categorie": "Running", "zone": "RUNNING"},
    {"id": "P006", "name": "Gilet de trail Evadict Homme", "categorie": "Trail", "zone": "FIT HOMME"},
    {"id": "P007", "name": "Tapis de yoga confort 8mm", "categorie": "Fitness", "zone": "FIT FEMME"},
    {"id": "P008", "name": "Doudoune Trekking MT100 Femme", "categorie": "Randonnee", "zone": "RANDONNEE"},
    {"id": "P009", "name": "Batons de marche Trail 500", "categorie": "Randonnee", "zone": "RANDONNEE"},
    {"id": "P010", "name": "Lanterne rechargeable BL200", "categorie": "Camping", "zone": "CAMPING"},
]

questions = [
    "Pouvez-vous me conseiller une tente pour 3 personnes ?",
    "Quel velo est adapte pour les chemins de foret ?",
    "Je cherche un sac a dos leger pour la randonnee.",
    "Quelle montre GPS conseillez-vous pour courir ?",
    "Je veux une lampe pratique pour le camping.",
    "Quel produit pour un trek de 3 jours ?",
]

responses = [
    "Je vous recommande la tente MH500, ideale pour 3 personnes.",
    "Le velo Rockrider ST530 est parfait pour les chemins forestiers.",
    "Le sac Forclaz 40L est leger et confortable pour les longues marches.",
    "La montre Garmin Instinct 2 est parfaite pour suivre vos performances.",
    "La lanterne BL200 est puissante et facile a recharger.",
    "Pour un trek, la doudoune MT100 et le sac Forclaz sont parfaits.",
]

# --- Génération des données réalistes sur une semaine ---
for i in range(7):  # 7 jours
    date = timezone.now() - timedelta(days=i)
    nb_sessions = random.randint(8, 15)
    for j in range(nb_sessions):
        duree = timedelta(seconds=random.randint(120, 480))
        start = date - timedelta(minutes=random.randint(10, 120))
        end = start + duree

        # Création de session utilisateur
        session = Session.objects.create(
            user_id=f"client_{random.randint(1000, 9999)}",
            start_time=start,
            end_time=end,
            duration=duree,
            device=random.choice(devices),
            location=random.choice(magasins),
        )

        # Création de clics (provenant de la carte du magasin)
        for k in range(random.randint(4, 10)):
            prod = random.choice(produits)
            Click.objects.create(
                session=session,
                product_name=prod["name"],
                page=f"/produit/{prod['id']}/",
                timestamp=start + timedelta(seconds=random.randint(5, 120)),
            )

        # Enregistrement des vues produit (source = carte)
        for k in range(random.randint(1, 3)):
            prod = random.choice(produits)
            ProductView.objects.create(
                session=session,
                product_name=prod["name"],
                product_id=prod["id"],
                viewed_at=start + timedelta(seconds=random.randint(10, 180)),
                source="carte",
                zone=prod["zone"],
            )

        # Interactions chatbot (60% des sessions)
        if random.random() < 0.6:
            n_interactions = random.randint(1, 2)
            for _ in range(n_interactions):
                q_idx = random.randint(0, len(questions) - 1)
                ChatbotInteraction.objects.create(
                    session=session,
                    question=questions[q_idx],
                    response=responses[q_idx],
                    created_at=start + timedelta(seconds=random.randint(15, 200)),
                    model_used="Mistral",
                    satisfaction=random.choice([True, False, None]),
                )

print("Donnees de test coherentes et realistes inserees avec succes !")
