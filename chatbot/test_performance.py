"""
Script de test de performance pour le chatbot
Mesure les gains de performance des optimisations threadées
"""

import os
import sys
import django
import time
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liasec_hub.settings')
django.setup()

from chatbot.utils.vector_search import search_products
from chatbot.utils.scoring import compute_score
from chatbot.product_matcher import match_rec_to_vector_product
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_sequential_scoring(products, query):
    """Test du calcul séquentiel des scores (ancienne méthode)"""
    start = time.time()
    for p in products:
        p["score"] = compute_score(query, p)
    end = time.time()
    return end - start


def test_parallel_scoring(products, query):
    """Test du calcul parallèle des scores (nouvelle méthode)"""
    def compute_product_score(product, q):
        product["score"] = compute_score(q, product)
        return product

    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(compute_product_score, p, query) for p in products]
        results = [future.result() for future in as_completed(futures)]
    end = time.time()
    return end - start


def test_vector_search_performance():
    """Test de performance de la recherche vectorielle"""
    print("=" * 60)
    print("TEST DE PERFORMANCE - CHATBOT OPTIMISÉ")
    print("=" * 60)

    query = "chaussure de running pour homme confortable"

    # Test 1: Recherche vectorielle avec k=2000 (optimisé)
    print("\n[TEST 1] Recherche vectorielle (k=2000 - optimise)")
    start = time.time()
    products_2k = search_products(query, k=2000)
    time_2k = time.time() - start
    print(f"  >> Temps: {time_2k:.3f}s pour {len(products_2k)} produits")

    # Test 2: Calcul des scores - Séquentiel vs Parallèle
    print("\n[TEST 2] Calcul des scores")

    # Copie des produits pour les deux tests
    products_seq = [p.copy() for p in products_2k[:500]]  # Limiter à 500 pour le test
    products_par = [p.copy() for p in products_2k[:500]]

    time_seq = test_sequential_scoring(products_seq, query)
    print(f"  - Sequentiel: {time_seq:.3f}s pour 500 produits")

    time_par = test_parallel_scoring(products_par, query)
    print(f"  - Parallele (8 threads): {time_par:.3f}s pour 500 produits")

    speedup = time_seq / time_par if time_par > 0 else 0
    improvement = ((time_seq - time_par) / time_seq * 100) if time_seq > 0 else 0
    print(f"  >> Gain: {speedup:.2f}x plus rapide ({improvement:.1f}% d'amelioration)")

    # Test 3: Matching de recommandations
    print("\n[TEST 3] Matching de recommandations")
    test_rec = {
        "nom": "Chaussures de running Homme GEL EXCITE 10",
        "reference": "123456"
    }

    start = time.time()
    matched = match_rec_to_vector_product(test_rec, products_2k)
    time_match = time.time() - start

    if matched:
        print(f"  >> Match trouve: {matched['title']}")
    print(f"  >> Temps de matching: {time_match:.3f}s")

    # Résumé
    print("\n" + "=" * 60)
    print("RESUME DES OPTIMISATIONS")
    print("=" * 60)
    print(f"1. Reduction de k: 15000 -> 2000 (7.5x moins de donnees)")
    print(f"2. Calcul parallele des scores: {speedup:.2f}x plus rapide")
    print(f"3. Matching parallele des recommandations: Active")
    print(f"4. ThreadPoolExecutor: 8 workers pour scoring, 4 pour matching")
    print("\n>> Les reponses du chatbot devraient etre significativement plus rapides!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_vector_search_performance()
    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()
