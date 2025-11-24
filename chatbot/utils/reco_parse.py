import re


def _parse_recommendations_md(text: str):
    """
    Extrait des recommandations même si le Markdown est mal formé
    (puces, espaces, variations de ![Image]).
    """
    recs = []
    # Découpe sur les débuts "1.", "2." etc.
    blocks = re.split(r'(?:^|\n)\s*\d+\.\s', text, flags=re.MULTILINE)
    for b in blocks:
        if "Produit" not in b:
            continue

        def extract(label):
            # supporte "- **Label :**", "**Label:**", etc.
            rx = re.compile(rf"[-•]?\s*\*\*\s*{label}\s*:\s*\*\*\s*(.+)", re.IGNORECASE)
            m = rx.search(b)
            return m.group(1).strip() if m else ""

        name = extract("Produit")
        brand = extract("Marque")
        price = extract("Prix")
        cat = extract("Catégorie|Categorie")
        feats = extract("Caractéristiques|Caracteristiques")

        # Capture du premier lien image, même s'il est mal formaté
        img_match = re.search(r"!\s*\[[^\]]*\]\s*\(([^)]+)\)", b)
        image_url = img_match.group(1).strip() if img_match else ""

        if name:
            recs.append({
                "name": name,
                "brand": brand,
                "price_text": price,
                "category": cat,
                "features": feats,
                "image_url": image_url,
            })

    print(f"[DEBUG] Parsing Markdown : {len(recs)} produits trouvés")
    for r in recs:
        print(f"  - {r['name']} | {r['price_text']} | {r['image_url'][:60]}...")
    return recs
