# chatbot/utils/vector_search.py

import threading
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from django.conf import settings
from sentence_transformers import SentenceTransformer


# ======================================================================
# 🔒 SINGLETON VECTOR STORE (index + metadata + model)
# ======================================================================

class _VectorStoreSingleton:
    """
    Singleton hautement optimisé pour :
    - charger FAISS une seule fois
    - charger les métadonnées une seule fois
    - charger le modèle d’embedding une seule fois
    Compatible multi-threads + Django + production
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        base_dir = Path(settings.BASE_DIR)
        vector_dir = base_dir / "vector_store"

        index_path = vector_dir / "index.faiss"
        meta_path = vector_dir / "metadata.parquet"

        # --------------------------------------------------
        # Charger FAISS
        # --------------------------------------------------
        print(f"[VECTOR] Chargement index FAISS depuis {index_path}")
        self.index = faiss.read_index(str(index_path))

        # Important si tu déploies sur CPU :
        if not faiss.get_num_gpus():
            faiss.omp_set_num_threads(8)

        # --------------------------------------------------
        # Charger les métadonnées
        # --------------------------------------------------
        print(f"[VECTOR] Chargement métadonnées depuis {meta_path}")
        self.metadata = pq.read_table(str(meta_path)).to_pandas()

        # Vérification des colonnes
        required_cols = {
            "reference", "Title", "Brand", "sub_category",
            "Sport", "Price", "Features", "image_1", "image_2"
        }
        if not required_cols.issubset(self.metadata.columns):
            raise ValueError(f"Métadonnées vector store invalides. Colonnes manquantes.")

        # --------------------------------------------------
        # Charger le modèle d’embedding
        # --------------------------------------------------
        print("[VECTOR] Chargement du modèle d'embedding (all-MiniLM-L6-v2 normalisé)")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self._initialized = True

    # ==================================================================
    # 🔎 FONCTION DE RECHERCHE PRINCIPALE
    # ==================================================================
    def search(self, query: str, k: int = 20):
        """
        Recherche FAISS optimisée :
        - embeddings normalisés (cosine)
        - k peut monter à 5000 sans risque
        - retourne liste de dict produits
        """

        if not query:
            return []

        # --------------------------------------------------
        # Encoder la requête
        # --------------------------------------------------
        query_vector = self.model.encode(
            [query],
            normalize_embeddings=True
        )
        query_vector = np.asarray(query_vector, dtype="float32")

        # --------------------------------------------------
        # FAISS SEARCH
        # --------------------------------------------------
        try:
            distances, indices = self.index.search(query_vector, k)
        except Exception as e:
            print(f"[VECTOR][ERREUR] Échec de la recherche FAISS : {e}")
            return []

        results = []

        # --------------------------------------------------
        # Reconstruction produits
        # --------------------------------------------------
        for idx in indices[0]:
            if idx < 0 or idx >= len(self.metadata):
                continue

            row = self.metadata.iloc[idx]

            # robustesse prix
            try:
                price = float(row["Price"])
            except Exception:
                price = None

            product = {
                "reference": str(row["reference"]).strip(),
                "title": row["Title"],
                "brand": row["Brand"],
                "sub_category": row["sub_category"],
                "sport": row.get("Sport", ""),
                "price": price,
                "features": row.get("Features", ""),
                "image_1": row.get("image_1", ""),
                "image_2": row.get("image_2", ""),
            }

            results.append(product)

        return results


# ================================================================
# Instance globale — importable dans tout Django
# ================================================================
vector_store = _VectorStoreSingleton()


# ================================================================
# API simple à utiliser dans views.py
# ================================================================
def search_products(query: str, k: int = 20):
    return vector_store.search(query, k=k)
