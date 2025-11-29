from dashboard.models import Session, Product, ProductView, Click, ChatbotInteraction, ChatbotRecommendation, Settings
from django.utils import timezone
from datetime import timedelta
import random

# Nettoyage de la base pour repartir propre
Session.all_objects.all().delete()
Product.objects.all().delete()
ProductView.all_objects.all().delete()
Click.all_objects.all().delete()
ChatbotInteraction.all_objects.all().delete()
ChatbotRecommendation.all_objects.all().delete()
Settings.objects.all().delete()

# ======================
# ⚙️ Paramètres globaux
# ======================
Settings.objects.create(
    name="Borne tactile v2.1",
    location="Decathlon Le Mans",
    code="BNL-021",
    track_sessions=True,
    track_clicks=True,
    track_chatbot=True
)

# ======================
# 🛒 Produits
# ======================
products = [
    Product.objects.create(
        product_id=f"P{i:03}",
        name=name,
        description=f"Description du produit {name.lower()} pour les tests.",
        category=category,
        price=price,
        available=random.choice([True, True, False]),
        image_url=f"https://picsum.photos/seed/{i}/200/200",
        brand=random.choice(["Kipsta", "Domyos", "Quechua", "Artengo"]),
    )
    for i, (name, category, price) in enumerate([
        ("T-shirt respirant homme", "FIT HOMME", 12.99),
        ("Chaussures de running femme", "CHAUSSANT", 49.99),
        ("Veste imperméable randonnée", "RANDONNÉE", 79.99),
        ("Raquette de tennis adulte", "SPORTS DE RAQUETTE", 29.99),
        ("Ballon de football taille 5", "COLLECTIF", 15.99),
        ("Short de fitness", "FIT HOMME", 9.99),
        ("Tapis de yoga", "BIEN-ÊTRE", 24.99),
        ("Casque de vélo", "CYCLISME", 39.99),
    ])
]

print(f"✅ {len(products)} produits créés.")

# ======================
# 👤 Sessions utilisateurs
# ======================
sessions = []
for i in range(10):
    start = timezone.now() - timedelta(hours=random.randint(1, 48))
    end = start + timedelta(minutes=random.randint(3, 45))
    s = Session.objects.create(
        user_id=f"user_{i}",
        start_time=start,
        end_time=end,
        duration=end - start,
        device=random.choice(["iPad Pro", "Surface Go", "PC borne tactile"]),
        location="Decathlon Le Mans",
    )
    sessions.append(s)
print(f"✅ {len(sessions)} sessions créées.")

# ======================
# 🖱️ Clics
# ======================
for session in sessions:
    for _ in range(random.randint(2, 6)):
        Click.objects.create(
            session=session,
            product_name=random.choice(products).name,
            page=random.choice(["accueil", "carte", "fiche produit", "chatbot"]),
            timestamp=timezone.now() - timedelta(minutes=random.randint(1, 120))
        )
print("✅ Clics enregistrés.")

# ======================
# 👀 Vues produit
# ======================
for session in sessions:
    for _ in range(random.randint(1, 4)):
        ProductView.objects.create(
            session=session,
            product=random.choice(products),
            viewed_at=timezone.now() - timedelta(minutes=random.randint(5, 180)),
            source=random.choice(["carte", "recherche", "chatbot"]),
            zone=random.choice(["FIT HOMME", "CHAUSSANT", "RANDONNÉE", "CYCLISME"])
        )
print("✅ Vues produits enregistrées.")

# ======================
# 🤖 Interactions chatbot
# ======================
for session in sessions:
    for _ in range(random.randint(1, 3)):
        question = random.choice([
            "Je cherche un t-shirt pour courir",
            "Quelle veste pour la pluie ?",
            "Un ballon de foot taille 5 ?",
            "Quel tapis de yoga me recommandes-tu ?",
            "Chaussures de running pour femme ?",
        ])
        response = random.choice([
            "Je te recommande le t-shirt respirant Kipsta.",
            "Essaie la veste imperméable Quechua.",
            "Le ballon Kipsta taille 5 est idéal.",
            "Regarde le tapis de yoga Domyos.",
            "Ces chaussures de running sont parfaites pour femme.",
        ])
        interaction = ChatbotInteraction.objects.create(
            session=session,
            question=question,
            response=response,
            satisfaction=random.choice([True, False, None]),
            model_used="Mistral-small"
        )

        # Liens vers recommandations réelles
        recommended_product = random.choice(products)
        ChatbotRecommendation.objects.create(
            session=session,
            interaction=interaction,
            product=recommended_product,
            recommended_at=timezone.now()
        )
print("✅ Interactions chatbot + recommandations créées.")

print("\n🎉 Jeu de données de test entièrement généré !")
print(f"Produits : {Product.objects.count()}")
print(f"Sessions : {Session.objects.count()}")
print(f"Interactions chatbot : {ChatbotInteraction.objects.count()}")
print(f"Recommandations : {ChatbotRecommendation.objects.count()}")
