from django.db.models import Q
from fuzzywuzzy import fuzz
from .query_parser import (
    extract_sport_category_from_query,
    infer_product_type_from_query,
    extract_colors_from_query,
    extract_gender_from_query,
    extract_age_group_from_query,
    extract_budget_from_query,
    extract_usage_keywords_from_query,
    normalize_text
)
from .constants import PRODUCT_TYPE_KEYWORDS, COLOR_KEYWORDS, GENDER_KEYWORDS, AGE_KEYWORDS


def safe_float(val):
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return None


def filter_products_for_query(question, products, top_k=30):
    if not products:
        return []

    question_norm = question.lower()

    sport = extract_sport_category_from_query(question)
    product_type = infer_product_type_from_query(question)

    if product_type:
        type_keywords = PRODUCT_TYPE_KEYWORDS.get(product_type, [])
        before = len(products)

        def match_type(p):
            text = (
                (p.get("title", "") + " " +
                 p.get("sub_category", "") + " " +
                 p.get("sport", "") + " " +
                 p.get("features", ""))
                .lower()
                .replace("-", " ")
                .replace("_", " ")
            )

            tokens = set(text.split())

            return any(
                kw == t or kw in tokens
                for kw in type_keywords
                for t in tokens
            )

        products = [p for p in products if match_type(p)]

        print(f"[FILTER] Filtrage strict par type '{product_type}' : {before} → {len(products)} produits")

    colors = extract_colors_from_query(question)
    gender = extract_gender_from_query(question)
    age = extract_age_group_from_query(question)
    budget = extract_budget_from_query(question)
    usage = extract_usage_keywords_from_query(question)

    q_tokens = [w for w in question_norm.split() if len(w) > 3]

    scored = []

    for p in products:
        txt = (
            f"{p.get('title', '')} "
            f"{p.get('sub_category', '')} "
            f"{p.get('sport', '')} "
            f"{p.get('features', '')}"
        ).lower()

        score = 0

        if sport and sport.lower() in txt:
            score += 4

        if product_type:
            kws = PRODUCT_TYPE_KEYWORDS.get(product_type, [])
            if any(k in txt for k in kws):
                score += 5

        if colors:
            for c in colors:
                for kw in COLOR_KEYWORDS.get(c, []):
                    if kw in txt:
                        score += 2

        if gender:
            if any(kw in txt for kw in GENDER_KEYWORDS[gender]):
                score += 2

        if age:
            if any(kw in txt for kw in AGE_KEYWORDS[age]):
                score += 2

        if usage:
            if any(u in txt for u in usage):
                score += 3

        price = safe_float(p.get("price"))
        if budget is not None and price is not None:
            if price <= budget:
                score += 3
            else:
                score -= 1

        for token in q_tokens:
            if token in txt:
                score += 1

        title = p.get("title", "")
        fuzzy = fuzz.partial_ratio(question.lower(), title.lower())

        if fuzzy >= 70:
            score += 2
        if fuzzy >= 85:
            score += 4

        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    if len(scored) > top_k:
        top_slice = scored[:top_k]
        max_score = top_slice[0][0]

        extended = [item for item in scored if item[0] == max_score]

        if len(extended) > len(top_slice):
            top_slice = extended

        filtered = [p for s, p in top_slice]
    else:
        filtered = [p for s, p in scored]

    print(f"[FILTER] {len(filtered)} produits retenus (scoring intelligent).")
    return filtered


def build_product_filters(question, user_profile=None):
    filters = Q()

    sport = extract_sport_category_from_query(question)
    if sport:
        filters &= Q(sport__iexact=sport) | Q(category__icontains=sport)

    product_type = infer_product_type_from_query(question)
    if product_type:
        type_filter = Q()
        for keyword in [product_type]:
            type_filter |= Q(name__icontains=keyword) | Q(category__icontains=keyword)
        filters &= type_filter

    colors = extract_colors_from_query(question)
    if colors:
        color_filter = Q()
        for color in colors:
            color_filter |= Q(name__icontains=color)
        filters &= color_filter

    gender = extract_gender_from_query(question)
    if gender:
        filters &= Q(name__icontains=gender) | Q(category__icontains=gender)

    age = extract_age_group_from_query(question)
    if age:
        filters &= Q(name__icontains=age) | Q(category__icontains=age)

    budget = extract_budget_from_query(question)
    if budget:
        filters &= Q(price__lte=budget)

    if user_profile:
        if hasattr(user_profile, 'preferred_sport') and user_profile.preferred_sport:
            filters &= Q(sport__iexact=user_profile.preferred_sport)

        if hasattr(user_profile, 'max_budget') and user_profile.max_budget:
            filters &= Q(price__lte=user_profile.max_budget)

    return filters