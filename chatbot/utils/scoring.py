from fuzzywuzzy import fuzz

def compute_score(query, product):
    """
    Score hybride :
    - similarité vectorielle (déjà implicite car k=2000)
    - similarité lexicale du titre
    - bonus sur le respect du type (chaussure, t-shirt...)
    """
    q = query.lower()
    title = (product.get("title") or "").lower()

    # Similarité lexicale
    lexical = fuzz.token_set_ratio(q, title)

    # Bonus type produit
    bonus = 0
    if any(x in q for x in ["chaussure", "baskets", "sneakers"]):
        if "chauss" in title or "basket" in title:
            bonus += 10

    return lexical + bonus
