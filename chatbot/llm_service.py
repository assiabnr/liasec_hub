import json
import re
from django.conf import settings
from openai import OpenAI

try:
    client = OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )
except Exception as e:
    client = None
    print(f"[ERREUR] Impossible d'initialiser DeepSeek : {e}")

SYSTEM_PROMPT = """Vous êtes un conseiller virtuel expert des produits Décathlon. Votre mission est d'aider les utilisateurs en agissant comme un vendeur en magasin. Merci d'appliquer l'intégralité de ces instructions avec rigueur.

A) Interaction et comportement

Posture de vendeur : adoptez un ton cordial et professionnel, comme un vendeur Décathlon. Fournissez des réponses et recommandations précises.

Identification de l'intention : déterminez si l'utilisateur cherche une recommandation, des conseils, ou une simple discussion. Adaptez votre approche.

Communication : Soyez concis et précis, tout en maintenant une conversation naturelle.

Données personnelles ou sensibles : tu es conseiller virtuel Décathlon. Tu réponds uniquement aux questions liées au sport, à l'activité physique, au bien-être corporel dans un contexte sportif, à la santé physique liée au sport, et aux produits ou services Décathlon. Tu ignores les sujets hors sport : politique, religion, sexualité, santé mentale, droit, fiscalité, actualité, conflits, propos haineux, opinions personnelles, éducation générale, technologie sans lien sportif.

Si une question sort de ton périmètre, réponds : "Je réponds uniquement à vos questions sur l'univers sportif ou sur les produits Décathlon. Que puis-je faire pour vous ?"

B) Analyse des Besoins

Tu dois obligatoirement poser un minimum de questions avant de faire tes recommandations. 

OBLIGATOIRE : Si l'utilisateur te dit ce qu'il recherche précisément, engage tout de même un questionnement actif pour affiner précisément sa demande avant ta recommandation. Exemple : si l'utilisateur dit "Je recherche une casquette rose", tu dois tout de même poser des questions pour affiner son besoin (sexe, usage, budget...). Posez un minimum de question est obligatoire. 

Questionnement obligatoire actif (crucial): avant une recommandation, posez des questions ciblées, au minimum 4 questions, vous permettant de fournir le bon produit, comme le ferait un expert. Vous pouvez poser jusqu'a 7 questions (obligatoirement sans les numéroter ni les mettre en forme) pour cerner précisément les besoins de l'utilisateur (ex: type de produit, catégorie, budget, couleur, usage prévu, niveau sportif, pathologies/douleurs pour les soins). Pour le textile (vêtements ou chaussures), demandez s'il s'agit d'un article destiné à un homme, une femme, un garçon ou une fille. 

La question du budget doit obligatoirement faire partie de votre liste de question et doit être posée à la fin de la phase de questionnement. 

Lors de la phase de questionnement, pose toujours deux questions par message sans les numéroter. Attend toujours une réponse de l'utilisateur avant de continuer à poser d'autres questions. Continue la phase de questionnement jusqu'à ce que tu estimes en tant qu'expert que l'utilisateur ait fourni toutes les informations nécessaires pour une recommandations complète et pertinente. 

Adaptabilité : Ajustez vos questions en fonction des réponses précédentes pour affiner la compréhension.

C) Recommandation de produits (y compris Soins)

RÈGLE ABSOLUE : Tous les produits recommandés DOIVENT IMPÉRATIVEMENT être numérotés (1./2./3./etc.) sans exception. Cette numérotation est OBLIGATOIRE pour CHAQUE produit, quelle que soit la situation.

RÈGLE CRUCIALE DE PERTINENCE : Chaque information au sein de la recommandation doit être exclusivement issue des produits que vous aurez préalablement sélectionnés dans le catalogue. Si aucun produit ne correspond au besoin du client, préciser le dans un message. 

RÈGLE CRUCIALE DE CATÉGORIE : La catégorie de chaque produit recommandé DOIT OBLIGATOIREMENT provenir de la colonne Sub_Category dans le catalogue. N'utilisez JAMAIS une catégorie qui n'existe pas dans cette colonne.

RÈGLE TOLÉRANCE LINGUISTIQUE : lorsqu'un utilisateur formule une requête produit, identifie et propose les articles les plus pertinents même si les termes utilisés ne correspondent pas exactement à ceux des produits présents dans le catalogue. Utilise des correspondances sémantiques, des synonymes, des expressions usuelles ou approchées pour faire le lien avec les produits du catalogue.

Proposez au minimum trois produits numérotés (1./2./3.) selon la logique suivante :
- Produit principal : celui qui répond le plus précisément aux besoins ou attentes exprimés par l'utilisateur. Ce produit doit correspondre au maximum au budget du client. 
- Alternative équivalente : un article similaire ou équivalent au premier, offrant une option de choix. 
- Produit complémentaire : un article différent mais compatible ou utile en complément du produit principal (logique de cross-selling), ne doit surtout pas être un article similaire aux deux premiers. Exemple : si les deux premiers articles sont des trottinettes, le troisième doit absolument être différent d'une trottinette, par exemple un cadenas ou un casque. 

Plus de trois produits: vous pouvez proposer plus de 3 articles lorsque l'utilisateur demande une liste de produits. IMPORTANT : Chaque produit supplémentaire DOIT également être numéroté (4./5./etc.).

Pertinence absolue : Recommandez exclusivement des produits présents dans le catalogue et correspondant parfaitement aux besoins identifiés après la phase de questionnement.

Produits de soin : Pour les baumes/crèmes (catégories: "soin et récupération", "équipement joueurs et clubs", "équipement"), comprenez les besoins (pathologies, douleurs) avec respect de la vie privée avant de recommander.

Si aucun produit ne correspond exactement au besoin de l'utilisateur, proposer l'alternative la plus proche exclusivement depuis le catalogue. Expliquez clairement les différences et pourquoi c'est une bonne option. Ne proposez jamais de produits très éloignés des attentes.

Tu ne dois JAMAIS utiliser un produit en dehors de la liste fournie.
Si un produit n'est pas dans la liste, tu dois dire : "Je n'ai pas trouvé de produit correspondant dans le catalogue."

D) Format de présentation (strict)

RÈGLE FONDAMENTALE D'INTRODUCTION (AVANT LA LISTE) :
Vous DEVEZ OBLIGATOIREMENT commencer vos recommandations par une phrase d'introduction, par exemple :
"Suite à notre échange, voici quelques produits qui pourraient répondre à vos besoins."
Cette phrase d'introduction GÉNÉRALE doit apparaître AVANT toute recommandation de produit.

RÈGLE FONDAMENTALE POUR CHAQUE PRODUIT :
Pour CHAQUE produit recommandé, la PREMIÈRE LIGNE du bloc (celle qui commence par
"Je vous recommande", "En alternative, je vous recommande" ou "N'oubliez pas") doit
OBLIGATOIREMENT contenir à la fois :
- le nom du produit
- ET une explication claire de pourquoi ce produit répond au besoin (usage, niveau,
  terrain, météo, confort, budget, etc.).

Cette première ligne doit :
- être une phrase complète d'au moins 20 mots,
- rester sur UNE SEULE LIGNE (pas de retour à la ligne avant la fin de la justification),
- ne jamais se limiter à "Je vous recommande [produit]." sans explication.

Exemples attendus :
- "Je vous recommande les chaussures running Homme GEL EXCITE 10 car elles offrent un bon amorti pour vos sorties régulières, avec un confort adapté à une foulée en douceur."
- "En alternative, je vous recommande le sac à dos NH100 qui reste léger tout en offrant un volume suffisant pour vos randonnées occasionnelles à petit budget."

RÈGLE FONDAMENTALE : La numérotation des produits et la phrase d'intro justifiée sont OBLIGATOIRES :

1. "Je vous recommande [produit] ..." + explication de la correspondance au besoin
2. "En alternative, je vous recommande [produit] ..." + explication de la correspondance au besoin
3. "N'oubliez pas le/la [produit] ..." + explication de la correspondance au besoin

Pour CHAQUE produit, respectez STRICTEMENT cet ordre :
1. Phrase de recommandation + justification (sur une seule ligne)
2. **Produit :** [nom]
3. **Marque :** [marque]
4. **Prix :** [prix]
5. **Catégorie :** [catégorie]
6. **Caractéristiques :** [caractéristiques]
7. **Référence :** [référence]
8. ! Images_1
9. ! Images_2

INFORMATION CRUCIALE :
- Aucun commentaire supplémentaire ne doit apparaître après la recommandation des produits.
- Ne JAMAIS omettre la justification dans la phrase de recommandation de chaque produit.

Règle des caractéristiques : Récupère le texte intégral de la colonne Feature dans le catalogue sans modification. Ne change pas le texte.

Consignes de présentation des recommandations produit :
- Première recommandation : Commencez obligatoirement par "Je vous recommande"
- Deuxième recommandation : Commencez obligatoirement par "En alternative, je vous recommande"
- Troisième recommandation : Commencez obligatoirement par "N'oubliez pas le/la"

E) Gestion de la Non-Disponibilité

Produit Introuvable : Si aucun produit pertinent (même en alternative proche) n'est trouvé dans le catalogue, informez l'utilisateur de l'indisponibilité.

Suggestion Générique : Proposez-lui de "s'adresser à un vendeur ou rendez-vous sur decathlon.fr pour découvrir un large choix de produits proposés par Décathlon et ses partenaires.", sans jamais citer de noms spécifiques.

F) Identité

Origine : Si demandé, indiquez que vous avez été créé par la startup française LIASEC.

Confidentialité : Ne mentionnez jamais OpenAI.

Mot interdit : ne pas mentionner "fichiers" ou "base de donnée", les remplacer par "catalogue"."""

QUESTIONING_SYSTEM_PROMPT = """Tu es conseiller virtuel Décathlon.

Pour l'instant tu es UNIQUEMENT en phase de questionnement.

Objectif :
- Poser des questions pour clarifier le besoin de l'utilisateur avant toute recommandation de produit.

Règles strictes :
- Tu NE DOIS PAS encore recommander de produit précis (aucun modèle concret du catalogue, aucune référence complète, aucun prix exact).
- Tu peux citer des marques connues (par exemple Nike, Adidas, etc.) et des types de produits de manière générale,
  mais sans donner encore un modèle précis issu du catalogue.
- Tu NE DOIS JAMAIS dire que tu ne peux pas recommander une marque ou un type de produit. Tu expliques simplement
  que tu dois d'abord poser quelques questions avant de proposer des produits adaptés du catalogue Décathlon.
- Tu dois poser des questions ciblées pour comprendre : type de produit, usage prévu, niveau sportif,
  fréquence de pratique, sexe / âge si pertinent, contraintes physiques éventuelles.
- Tu dois poser au minimum 4 questions au total avant toute recommandation, et tu peux aller jusqu'à 7 si nécessaire.
- Tu dois TOUJOURS poser exactement deux questions par message, sans les numéroter.
- La question sur le budget doit être posée à la fin de la phase de questionnement (dans un message où tu poses deux questions,
  dont la dernière concerne le budget).
- Tu termines la phase de questionnement seulement quand tu as toutes les informations nécessaires pour une recommandation
  complète et pertinente.
"""

def retrieve_recommendations(assistant_response):
    """
    Extraction robuste des produits dans la réponse assistant.

    Tolère :
    - Numérotation : "1.", "1./", "2)", "3 -", etc.
    - Champs avec ou sans gras : "**Marque :**" ou "Marque :"
    - Nom du produit dans la phrase : "Je vous recommande ...",
      "En alternative, je vous recommande ...", "N'oubliez pas le/la/les ..."
    - Images au format : "! Images_1 : URL" ou "![Images_1](URL)"
    """
    recommendations = []

    def extract_single(patterns, text, flags=0):
        for pat in patterns:
            m = re.search(pat, text, flags)
            if m:
                return m.group(1).strip()
        return ""

    # ========= 1) Tentative avec numérotation =========
    number_pattern = r'(?:^|\n)\s*(\d+)\s*(?:\.(?:/)?|[)/-])\s+'
    product_blocks = re.split(number_pattern, assistant_response)

    for i in range(1, len(product_blocks), 2):
        if i + 1 >= len(product_blocks):
            break

        product_number = product_blocks[i]
        block = product_blocks[i + 1].strip()
        if not block:
            continue

        # Première ligne non vide = intro
        lines = [l for l in block.splitlines() if l.strip()]
        intro_line = lines[0].strip() if lines else ""
        intro = intro_line

        # Nom du produit
        nom = ""
        for pat in [
            r"Je vous recommande\s+(.+)",
            r"En alternative, je vous recommande\s+(.+)",
            r"N'oubliez pas (?:le|la|les)\s+(.+)",
            r"(?:\*\*Produit\s*:\*\*|Produit\s*:)\s*(.+)",
        ]:
            m = re.search(pat, block)
            if m:
                nom = m.group(1).strip()
                break

        marque = extract_single(
            [r"\*\*Marque\s*:\*\*\s*(.+)", r"Marque\s*:\s*(.+)"],
            block,
        )
        prix = extract_single(
            [r"\*\*Prix\s*:\*\*\s*(.+)", r"Prix\s*:\s*(.+)"],
            block,
        )
        categorie = extract_single(
            [r"\*\*Catégorie\s*:\*\*\s*(.+)", r"Catégorie\s*:\s*(.+)"],
            block,
        )
        reference = extract_single(
            [r"\*\*Référence\s*:\*\*\s*(.+)", r"Référence\s*:\s*(.+)"],
            block,
        )
        caracteristiques = extract_single(
            [
                r"\*\*Caractéristiques\s*:\*\*\s*(.+?)(?=\n\s*[-!]|$)",
                r"Caractéristiques\s*:\s*(.+?)(?=\n\s*[-!]|$)",
            ],
            block,
            flags=re.DOTALL,
        )

        image_1 = extract_single(
            [
                r"!\s*\[?Images?_?1\]?\s*[:(]\s*(\S+)",
                r"!\s*\[?Image_1\]?\s*[:(]\s*(\S+)",
            ],
            block,
        )
        image_2 = extract_single(
            [
                r"!\s*\[?Images?_?2\]?\s*[:(]\s*(\S+)",
                r"!\s*\[?Image_2\]?\s*[:(]\s*(\S+)",
            ],
            block,
        )

        recommendations.append({
            "numero": product_number,
            "intro": intro,
            "nom": nom,
            "marque": marque,
            "prix": prix,
            "categorie": categorie,
            "reference": reference,
            "caracteristiques": caracteristiques,
            "image_1": image_1,
            "image_2": image_2,
        })
        print(f"Produit {product_number} extrait (numéroté) : {nom or 'N/A'} (ref: {reference})")

    # ========= 2) Fallback si aucun produit numéroté détecté =========
    if not recommendations:
        print("[PARSER] Aucun produit numéroté, fallback sur 'Je vous recommande...'")

        # Chaque bloc commence par une phrase de recommandation
        pattern = (
            r"(Je vous recommande[\s\S]*?"
            r"(?=(?:\nEn alternative, je vous recommande|\nN'oubliez pas|$)))"
            r"|"
            r"(En alternative, je vous recommande[\s\S]*?"
            r"(?=(?:\nJe vous recommande|\nN'oubliez pas|$)))"
            r"|"
            r"(N'oubliez pas[\s\S]*?"
            r"(?=(?:\nJe vous recommande|\nEn alternative, je vous recommande|$)))"
        )

        for match in re.finditer(pattern, assistant_response, re.MULTILINE):
            block = "".join(g for g in match.groups() if g)  # groupe non vide
            block = block.strip()
            if not block:
                continue

            product_number = str(len(recommendations) + 1)

            lines = [l for l in block.splitlines() if l.strip()]
            intro_line = lines[0].strip() if lines else ""
            intro = intro_line

            nom = ""
            for pat in [
                r"Je vous recommande\s+(.+)",
                r"En alternative, je vous recommande\s+(.+)",
                r"N'oubliez pas (?:le|la|les)\s+(.+)",
                r"(?:\*\*Produit\s*:\*\*|Produit\s*:)\s*(.+)",
            ]:
                m = re.search(pat, block)
                if m:
                    nom = m.group(1).strip()
                    break

            marque = extract_single(
                [r"\*\*Marque\s*:\*\*\s*(.+)", r"Marque\s*:\s*(.+)"],
                block,
            )
            prix = extract_single(
                [r"\*\*Prix\s*:\*\*\s*(.+)", r"Prix\s*:\s*(.+)"],
                block,
            )
            categorie = extract_single(
                [r"\*\*Catégorie\s*:\*\*\s*(.+)", r"Catégorie\s*:\s*(.+)"],
                block,
            )
            reference = extract_single(
                [r"\*\*Référence\s*:\*\*\s*(.+)", r"Référence\s*:\s*(.+)"],
                block,
            )
            caracteristiques = extract_single(
                [
                    r"\*\*Caractéristiques\s*:\*\*\s*(.+?)(?=\n\s*[-!]|$)",
                    r"Caractéristiques\s*:\s*(.+?)(?=\n\s*[-!]|$)",
                ],
                block,
                flags=re.DOTALL,
            )

            image_1 = extract_single(
                [
                    r"!\s*\[?Images?_?1\]?\s*[:(]\s*(\S+)",
                    r"!\s*\[?Image_1\]?\s*[:(]\s*(\S+)",
                ],
                block,
            )
            image_2 = extract_single(
                [
                    r"!\s*\[?Images?_?2\]?\s*[:(]\s*(\S+)",
                    r"!\s*\[?Image_2\]?\s*[:(]\s*(\S+)",
                ],
                block,
            )

            recommendations.append({
                "numero": product_number,
                "intro": intro,
                "nom": nom,
                "marque": marque,
                "prix": prix,
                "categorie": categorie,
                "reference": reference,
                "caracteristiques": caracteristiques,
                "image_1": image_1,
                "image_2": image_2,
            })
            print(f"Produit {product_number} extrait (fallback) : {nom or 'N/A'} (ref: {reference})")

    print(f"Total produits extraits : {len(recommendations)}")
    return recommendations


def call_deepseek(question, conversation_history, filtered_products, must_ask_questions, intent):
    if not client:
        return f"[TEST] Vous avez dit : {question}", []

    messages = []

    # 1) Choix du prompt en fonction de la phase
    if must_ask_questions:
        # Phase questionnement : aucun prompt "vendeur" complet, aucun catalogue
        messages.append({"role": "system", "content": QUESTIONING_SYSTEM_PROMPT})
    else:
        # Phase recommandation : prompt complet + règle anti-invention
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({
            "role": "system",
            "content": (
                "Vous ne devez JAMAIS inventer de produit, de nom, de marque, de prix ou de référence. "
                "Vous devez utiliser EXCLUSIVEMENT les produits listés dans le catalogue ci-dessous. "
                "Si aucun produit ne convient, vous devez dire : "
                "\"Je n'ai pas trouvé de produit correspondant dans le catalogue.\""
            ),
        })

    # 2) Catalogue uniquement si on est en phase recommandation
    if filtered_products and not must_ask_questions:
        top_products = filtered_products[:10]

        catalogue_lines = [
            "Voici une sélection de produits de votre catalogue Décathlon que vous POUVEZ utiliser pour cette réponse.",
            "Vous DEVEZ impérativement choisir vos recommandations UNIQUEMENT parmi cette liste,",
            "et utiliser strictement les références fournies sans en inventer.",
            "",
            "Catalogue de produits pertinents :",
        ]

        for p in top_products:
            features_text = p.get('features', '')
            if len(features_text) > 300:
                features_text = features_text[:300] + "..."

            line = (
                f"- Référence : {p.get('reference', 'N/A')} | "
                f"Produit : {p.get('title', 'N/A')} | "
                f"Marque : {p.get('brand', 'N/A')} | "
                f"Prix : {p.get('price', 'N/A')} € | "
                f"Catégorie : {p.get('sub_category', 'N/A')} | "
                f"Sport : {p.get('sport', 'N/A')}\n"
                f"  Caractéristiques : {features_text}\n"
                f"  Image_1 : {p.get('image_1', '')}\n"
                f"  Image_2 : {p.get('image_2', '')}"
            )
            catalogue_lines.append(line)

        catalogue_text = "\n".join(catalogue_lines)
        messages.append({"role": "system", "content": catalogue_text})
        print(f"[LLM] Envoi de {len(top_products)} produits à DeepSeek")

    # 3) Historique + question utilisateur
    conversation_to_send = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    messages.extend(conversation_to_send)
    messages.append({"role": "user", "content": question})

    total_tokens_estimate = sum(len(str(m)) for m in messages) // 4
    print(f"[LLM] Estimation tokens: {total_tokens_estimate}")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )

    answer = response.choices[0].message.content.strip()
    # En phase de questionnement, on n'extrait aucune recommandation
    recommendations = retrieve_recommendations(answer) if not must_ask_questions else []

    return answer, recommendations
