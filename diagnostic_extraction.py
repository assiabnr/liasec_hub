#!/usr/bin/env python3
"""
Script de diagnostic pour identifier pourquoi les produits ne sont pas enregistrés
"""

import re

# Réponse exacte du chatbot depuis les logs
response_text = """Suite à notre échange, voici quelques produits qui pourraient répondre à vos besoins :

1. Je vous recommande la « Chaussure de ville homme cuir noir - VILA » de Décathlon. C'est une chaussure de ville classique en cuir noir qui conviendra parfaitement pour un usage quotidien, avec un excellent rapport qualité-prix dans votre budget.

- **Produit :** Chaussure de ville homme cuir noir - VILA
- **Marque :** VILA
- **Prix :** 49,99 €
- **Catégorie :** Chaussures homme
- **Caractéristiques :** Chaussure de ville homme en cuir synthétique. Semelle extérieure en caoutchouc pour une bonne accroche. Semelle intérieure amovible. Confort immédiat.
- **Référence :** 8389991
- ! [Images_1] (https://contents.mediadecathlon.com/p2238768/k$7a0e6c0b...)
- ! [Images_2] (...)"""

print("=" * 80)
print("DIAGNOSTIC - Extraction des Recommandations")
print("=" * 80)

# Test 1 : Split par numéros
print("\n1️⃣  TEST SPLIT PAR NUMÉROS")
print("-" * 80)
product_blocks = re.split(r'\n\s*(\d+)\.\s+', response_text)
print(f"Nombre de blocs après split : {len(product_blocks)}")
for i, block in enumerate(product_blocks[:5]):  # Afficher les 5 premiers
    print(f"\n📦 Bloc {i}:")
    print(f"   Contenu : {block[:100]}...")

# Test 2 : Extraction des champs
print("\n\n2️⃣  TEST EXTRACTION DES CHAMPS")
print("-" * 80)

if len(product_blocks) >= 3:
    product_number = product_blocks[1]
    block = product_blocks[2]

    print(f"Numéro du produit : {product_number}")
    print(f"Contenu du bloc : {block[:200]}...\n")

    # Extraction phrase d'intro
    intro_match = re.search(r'^(.*?)(?=\n?-?\s*\*\*Produit)', block, re.DOTALL)
    intro = intro_match.group(1).strip() if intro_match else ""
    print(f"✅ Intro extraite : {intro[:100]}...")

    # Extraction des champs
    nom = re.search(r"\*\*Produit\s*:\*\*\s*(.+)", block)
    marque = re.search(r"\*\*Marque\s*:\*\*\s*(.+)", block)
    prix = re.search(r"\*\*Prix\s*:\*\*\s*(.+)", block)
    categorie = re.search(r"\*\*Catégorie\s*:\*\*\s*(.+)", block)
    reference = re.search(r"\*\*Référence\s*:\*\*\s*(.+)", block)

    print(f"\n✅ Nom : {nom.group(1).strip() if nom else 'NON TROUVÉ'}")
    print(f"✅ Marque : {marque.group(1).strip() if marque else 'NON TROUVÉ'}")
    print(f"✅ Prix : {prix.group(1).strip() if prix else 'NON TROUVÉ'}")
    print(f"✅ Catégorie : {categorie.group(1).strip() if categorie else 'NON TROUVÉ'}")
    print(f"✅ Référence : {reference.group(1).strip() if reference else 'NON TROUVÉ'}")

    if reference:
        ref = reference.group(1).strip()
        print(f"\n🔍 RÉFÉRENCE EXTRAITE : '{ref}'")
        print(f"   Type : {type(ref)}")
        print(f"   Longueur : {len(ref)}")
        print(f"   Est numérique ? {ref.isdigit()}")

# Test 3 : Vérification du format
print("\n\n3️⃣  TEST FORMAT DU TEXTE")
print("-" * 80)
if "**Produit" in response_text:
    print("✅ Contient '**Produit'")
if "**Référence" in response_text:
    print("✅ Contient '**Référence'")
if "**Marque" in response_text:
    print("✅ Contient '**Marque'")

# Compter les produits
products_count = len(re.findall(r'\n\s*\d+\.\s+', response_text))
print(f"\n📊 Nombre de produits détectés : {products_count}")

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)

print("\n\n💡 CONCLUSIONS:")
print("-" * 80)
print("Si tous les champs sont extraits correctement mais que product_count = 0,")
print("cela signifie que le produit avec cette référence N'EXISTE PAS dans la BD.")
print("\nVérifications à faire dans Django:")
print("1. python manage.py shell")
print("2. >>> from dashboard.models import Product")
print("3. >>> Product.objects.filter(product_id='8389991').exists()")
print("4. Si False → Le produit n'existe pas dans la BD !")
print("\n✅ SOLUTION : Importer les produits dans la BD Product")