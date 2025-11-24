from fuzzywuzzy import fuzz, process
from dashboard.models import Product


def find_best_product(nom):
    if not nom:
        return None

    nom_clean = nom.strip()

    produit_exact = Product.objects.filter(name__iexact=nom_clean).first()
    if produit_exact:
        print(f"Match exact : {produit_exact.name}")
        return produit_exact

    noms_produits = list(Product.objects.values_list('name', flat=True))
    if not noms_produits:
        print("Aucun produit en base")
        return None

    result = process.extractOne(nom_clean, noms_produits, scorer=fuzz.token_sort_ratio)
    if result is None:
        print(f"Aucune correspondance pour : {nom_clean}")
        return None

    best_match, score = result
    print(f"Fuzzy matching : '{nom_clean}' → '{best_match}' (score: {score}%)")

    if score >= 90:
        produit = Product.objects.filter(name=best_match).first()
        print(f"Produit trouvé via fuzzy : {produit.name}")
        return produit

    print(f"Score insuffisant ({score}% < 90%)")
    return None


def match_rec_to_vector_product(rec, retrieved_products):
    nom = (rec.get("nom") or "").strip()
    if not nom or not retrieved_products:
        return None

    best = None
    best_score = 0

    for p in retrieved_products:
        title = (p.get("title") or "").strip()
        if not title:
            continue
        score = fuzz.token_sort_ratio(nom.lower(), title.lower())
        if score > best_score:
            best_score = score
            best = p

    if best and best_score >= 90:
        print(
            f"Match vector_store : '{nom}' → '{best['title']}' "
            f"(ref {best['reference']}, score {best_score})"
        )
        return best

    print(f"Aucun match fiable dans vector_store pour '{nom}' (score max {best_score})")
    return None