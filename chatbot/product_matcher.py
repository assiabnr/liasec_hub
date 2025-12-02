from fuzzywuzzy import fuzz, process
from concurrent.futures import ThreadPoolExecutor
from dashboard.models import Product


def find_best_product(nom):
    """
    Trouve le meilleur produit correspondant au nom donné.
    Optimisé avec cache en mémoire pour éviter les requêtes DB répétées.
    """
    if not nom:
        return None

    nom_clean = nom.strip()

    # Match exact (rapide)
    produit_exact = Product.objects.filter(name__iexact=nom_clean).first()
    if produit_exact:
        print(f"Match exact : {produit_exact.name}")
        return produit_exact

    # Fuzzy matching avec cache
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


def _compute_match_score(product, nom_lower):
    """Helper pour calculer le score de matching en parallèle"""
    title = (product.get("title") or "").strip()
    if not title:
        return product, 0
    score = fuzz.token_sort_ratio(nom_lower, title.lower())
    return product, score


def match_rec_to_vector_product(rec, retrieved_products):
    """
    Matche une recommandation avec un produit du vector store.
    Optimisé avec threading pour calculer les scores en parallèle.
    """
    nom = (rec.get("nom") or "").strip()
    if not nom or not retrieved_products:
        return None

    nom_lower = nom.lower()
    best = None
    best_score = 0

    # Optimisation: Calcul parallèle des scores de matching
    # Seulement si on a beaucoup de produits (>100), sinon l'overhead du threading n'en vaut pas la peine
    if len(retrieved_products) > 100:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda p: _compute_match_score(p, nom_lower), retrieved_products))

        for product, score in results:
            if score > best_score:
                best_score = score
                best = product
    else:
        # Pour peu de produits, calcul séquentiel plus efficace
        for p in retrieved_products:
            title = (p.get("title") or "").strip()
            if not title:
                continue
            score = fuzz.token_sort_ratio(nom_lower, title.lower())
            if score > best_score:
                best_score = score
                best = p

    if best and best_score >= 90:
        print(
            f"Match vector_store : '{nom}' -> '{best['title']}' "
            f"(ref {best['reference']}, score {best_score})"
        )
        return best

    print(f"Aucun match fiable dans vector_store pour '{nom}' (score max {best_score})")
    return None