# scripts/create_vector_store.py

import os
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

# =====================================================================
# CONFIGURATION
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "deca_new_clean2.csv"

VECTOR_DIR = BASE_DIR / "vector_store"
VECTOR_DIR.mkdir(exist_ok=True)

INDEX_PATH = VECTOR_DIR / "index.faiss"
META_PATH = VECTOR_DIR / "metadata.parquet"

print("=======================================================")
print("🧠  CRÉATION DU VECTOR STORE DÉCATHLON (corrigé, dédupliqué)")
print("=======================================================\n")

# =====================================================================
# 1) CHARGEMENT DU CSV
# =====================================================================

print(f"[INFO] Chargement du CSV : {CSV_PATH}")

df = pd.read_csv(CSV_PATH, dtype=str).fillna("")

print(f"[INFO] Nombre total de produits dans le CSV : {len(df):,}")
print(f"[INFO] Colonnes détectées : {list(df.columns)}")

# =====================================================================
# NORMALISATION DES RÉFÉRENCES
# =====================================================================

def clean_reference(ref):
    if ref is None:
        return ""
    try:
        return str(int(float(ref)))  # "205435.0" → "205435"
    except Exception:
        return str(ref).strip()

df["reference_clean"] = df["Reference Number"].apply(clean_reference)

# =====================================================================
# 2) SUPPRESSION DES DOUBLONS **PAR RÉFÉRENCE**
# =====================================================================

before = len(df)
df = df[df["reference_clean"] != ""]
df = df.drop_duplicates(subset=["reference_clean"], keep="first")

after = len(df)

print(f"[INFO] Produits avant déduplication : {before:,}")
print(f"[INFO] Produits après déduplication : {after:,}")
print(f"[INFO] Doublons supprimés : {before - after:,}\n")

# Normaliser noms de colonnes
df.rename(
    columns={
        "Sub Category": "sub_category",
        "Images 1": "image_1",
        "Images 4": "image_2",
    },
    inplace=True
)

# =====================================================================
# 3) CONSTRUCTION DU TEXTE POUR EMBEDDINGS
# =====================================================================

def clean_text(x):
    if not x:
        return ""
    return str(x).replace("\n", " ").replace("\t", " ").strip()

def build_text(row):
    parts = [
        clean_text(row.get("Title", "")),
        clean_text(row.get("Brand", "")),
        clean_text(row.get("sub_category", "")),
        clean_text(row.get("Sport", "")),
        clean_text(row.get("Features", "")),
    ]
    return " ".join([p for p in parts if p])

df["text"] = df.apply(build_text, axis=1)

print("[INFO] Exemple de texte embedding :")
print(df["text"].iloc[0][:300], "\n")

# =====================================================================
# 4) EMBEDDINGS SENTENCE TRANSFORMERS
# =====================================================================

print("[INFO] Chargement du modèle all-MiniLM-L6-v2…")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("[INFO] Encodage des produits… (30–60 sec)")
embeddings = model.encode(
    df["text"].tolist(),
    show_progress_bar=True,
    normalize_embeddings=True
)

embeddings = np.asarray(embeddings, dtype="float32")

print(f"[INFO] Embeddings générés : shape = {embeddings.shape}")

# =====================================================================
# 5) CRÉATION INDEX FAISS
# =====================================================================

d = embeddings.shape[1]
print(f"[INFO] Création FAISS IndexFlatIP (dim={d})")

index = faiss.IndexFlatIP(d)
index.add(embeddings)

print(f"[INFO] Index FAISS créé avec {index.ntotal:,} vecteurs")

# =====================================================================
# 6) SAUVEGARDE
# =====================================================================

print(f"[INFO] Sauvegarde de l’index → {INDEX_PATH}")
faiss.write_index(index, str(INDEX_PATH))

meta_df = df[
    [
        "reference_clean",
        "Title",
        "Brand",
        "sub_category",
        "Sport",
        "Price",
        "Features",
        "image_1",
        "image_2",
    ]
].rename(columns={"reference_clean": "reference"})

print(f"[INFO] Sauvegarde des métadonnées → {META_PATH}")
pq.write_table(pa.Table.from_pandas(meta_df), str(META_PATH))

# =====================================================================
# FIN
# =====================================================================

print("\n=======================================================")
print("✅  VECTOR STORE GÉNÉRÉ SANS DOUBLONS")
print(f"🗂  Produits enregistrés : {len(meta_df):,}")
print(f"📁 Index : {INDEX_PATH}")
print(f"📄 Métadonnées : {META_PATH}")
print("=======================================================")
