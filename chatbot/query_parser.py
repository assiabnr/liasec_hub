import re
from .constants import (
    CATEGORIES_SPORT,
    PRODUCT_TYPE_KEYWORDS,
    COLOR_KEYWORDS,
    GENDER_KEYWORDS,
    AGE_KEYWORDS,
    USAGE_KEYWORDS
)


def normalize_text(text):
    if not text:
        return ""
    return text.lower()


def extract_sport_category_from_query(question):
    if not question:
        return None

    q_lower = question.lower()
    for cat in CATEGORIES_SPORT:
        if cat.lower() in q_lower:
            print(f"[FILTER] Sport détecté dans la requête : {cat}")
            return cat
    return None


def infer_product_type_from_query(question):
    if not question:
        return None

    q = question.lower()
    for product_type, keywords in PRODUCT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                print(f"[FILTER] Type de produit détecté dans la requête : {product_type}")
                return product_type
    return None


def extract_colors_from_query(question):
    if not question:
        return []

    q = question.lower()
    detected = []
    for color, kws in COLOR_KEYWORDS.items():
        if any(kw in q for kw in kws):
            detected.append(color)
    if detected:
        print(f"[FILTER] Couleurs détectées : {detected}")
    return detected


def extract_gender_from_query(question):
    if not question:
        return None
    q = question.lower()
    for gender, kws in GENDER_KEYWORDS.items():
        if any(kw in q for kw in kws):
            print(f"[FILTER] Genre détecté : {gender}")
            return gender
    return None


def extract_age_group_from_query(question):
    if not question:
        return None
    q = question.lower()
    for age, kws in AGE_KEYWORDS.items():
        if any(kw in q for kw in kws):
            print(f"[FILTER] Tranche d'âge détectée : {age}")
            return age
    return None


def extract_budget_from_query(question):
    if not question:
        return None

    q = question.lower()
    patterns = [
        r'(\d+[.,]?\d*)\s*€',
        r'budget[^0-9]*(\d+[.,]?\d*)',
        r'max[^0-9]*(\d+[.,]?\d*)',
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            try:
                val = float(m.group(1).replace(',', '.'))
                print(f"[FILTER] Budget détecté : {val} €")
                return val
            except Exception:
                continue
    return None


def extract_usage_keywords_from_query(question):
    if not question:
        return []

    q = question.lower()
    detected = []
    for kw in USAGE_KEYWORDS:
        if kw in q:
            detected.append(kw)
    if detected:
        print(f"[FILTER] Usages détectés : {detected}")
    return detected