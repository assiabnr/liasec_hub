from django.utils import timezone
from dashboard.models import ChatbotRecommendation
from .product_matcher import match_product_from_recommendation


def create_recommendation_record(session, interaction, product):
    ChatbotRecommendation.objects.create(
        session=session,
        interaction=interaction,
        product=product,
        recommended_at=timezone.now(),
    )
    print(f"Recommandation enregistrée en BD : {product.name}")


def format_product_json(product, recommendation):
    description = recommendation.get("intro", "")
    if not description:
        description = f"Je vous recommande ce produit {product.name}."

    return {
        "id": product.id,
        "reference": product.product_id,
        "product": product.name,
        "name": product.name,
        "brand": product.brand or "Décathlon",
        "price": f"{product.price:.2f} €" if product.price is not None else "",
        "category": product.category or "",
        "sport": product.sport or "",
        "imageUrl": product.image_url or "",
        "image_url": product.image_url or "",
        "imageUrlAlt": product.image_url_alt or "",
        "description": description,
        "productDescription": product.description or "",
        "features": [recommendation.get("caracteristiques", "")] if recommendation.get("caracteristiques") else (
            [product.description] if product.description else []
        ),
    }


def process_recommendations(recommendations, filtered_products, session, interaction):
    produits_json = []

    for rec in recommendations:
        product = match_product_from_recommendation(rec, filtered_products)

        if product:
            create_recommendation_record(session, interaction, product)
            produits_json.append(format_product_json(product, rec))
            print(f"Produit ajouté au JSON : {product.name} (ID: {product.id})")
        else:
            print(f"Produit non trouvé : {rec.get('nom', 'N/A')} (ref: {rec.get('reference', 'N/A')})")

    print(f"Total produits recommandés : {len(produits_json)}")
    print(f"Total enregistrements en BD : {ChatbotRecommendation.objects.filter(interaction=interaction).count()}")

    return produits_json