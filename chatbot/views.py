import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import uuid

from chatbot.utils.scoring import compute_score
from chatbot.utils.vector_search import search_products
from dashboard.models import (
    Session,
    ChatbotInteraction,
    ChatbotRecommendation,
    Product
)

from .constants import CATEGORIES_SPORT
from .query_parser import (
    extract_sport_category_from_query,
    infer_product_type_from_query,
)
from .product_filters import filter_products_for_query
from .llm_service import call_deepseek, retrieve_recommendations
from .product_matcher import find_best_product, match_rec_to_vector_product


def index_view(request):
    return render(request, "chatbot/index.html")


def tos_view(request):
    return render(request, "chatbot/tos.html")


def chat_view(request):
    """
    Affiche la page de chat sans toucher à la session.
    La fin de session est gérée par reset_chat (appelé par inactivity.js),
    et une nouvelle Session est créée au premier message (chat_api).
    """
    return render(request, "chatbot/chat.html")



@csrf_exempt
def check_session(request):
    try:
        session_id = request.session.get("session_id")

        if session_id:
            session = Session.objects.filter(id=session_id).first()
            if session:
                # On remet l'historique et le compteur à zéro si on réutilise cette session
                request.session["conversation_history"] = []
                request.session["questions_asked"] = 0

                return JsonResponse({
                    "success": True,
                    "session_id": session.id,
                    "message": "Session réinitialisée"
                })

        return JsonResponse({
            "success": True,
            "session_id": None,
            "message": "Aucune session active"
        })

    except Exception as e:
        print(f"[ERREUR] check_session : {e}")
        return JsonResponse({"error": str(e)}, status=500)


def accept_tos(request):
    try:
        if request.method == "POST":
            user_id = request.session.get("user_id") or str(uuid.uuid4())
            request.session["user_id"] = user_id

            request.session["conversation_history"] = []
            request.session["questions_asked"] = 0

            request.session.pop("session_id", None)

            return redirect("chatbot:chatbot_chat")

        return render(request, "chatbot/tos.html")

    except Exception as e:
        print(f"[ERREUR] accept_tos : {e}")
        return render(
            request,
            "chatbot/tos.html",
            {"error_message": "Une erreur est survenue. Veuillez réessayer."},
        )



def should_ask_questions(conversation_history):
    user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
    num_exchanges = len(user_messages)

    print(f"[QUESTIONING] Échanges utilisateur : {num_exchanges}")

    if num_exchanges < 2:
        print("[QUESTIONING] Phase questionnement (< 2 échanges)")
        return True

    assistant_messages = [msg for msg in conversation_history if msg.get("role") == "assistant"]
    if assistant_messages:
        last_bot_msg = assistant_messages[-1].get("content", "").lower()
        budget_keywords = ["budget", "prix", "dépenser", "combien", "€", "euro"]
        budget_asked = any(kw in last_bot_msg for kw in budget_keywords)

        if not budget_asked and num_exchanges < 4:
            print("[QUESTIONING] Budget pas demandé (continuer)")
            return True

        if user_messages:
            last_user_msg = user_messages[-1].get("content", "").lower()
            if any(phrase in last_user_msg for phrase in
                   ["pas de préférence", "pas de preference", "peu importe", "aucune préférence"]):
                if num_exchanges >= 2:
                    print("[QUESTIONING] Utilisateur sans préférence après 2 échanges - passage en recommandation")
                    return False

    if num_exchanges >= 3:
        print("[QUESTIONING] Prêt pour recommandation")
        return False

    if num_exchanges >= 4:
        print("[QUESTIONING] Max atteint (forcer reco)")
        return False

    return True


def infer_intent(question, conversation_history, filtered_products):
    import re

    q = (question or "").lower().strip()

    previous_user_texts = [
        m.get("content", "")
        for m in conversation_history
        if m.get("role") == "user"
    ]
    full_user_text = (" ".join(previous_user_texts) + " " + q).lower()
    full_clean = full_user_text.replace("'", " ")

    keywords = {
        "prix": ["prix", "coût", "cout", "combien", "tarif", "cher", "moins cher", "budget"],
        "taille": ["taille", "pointure", "format", "longueur", "largeur", "dimension"],
        "disponibilite": ["dispo", "stock", "restock", "en vente", "encore dispo", "rupture", "disponible"],
        "confirmation": ["oui", "non", "ok", "daccord", "d'accord"],
    }

    conseil_keywords = [
        "recherche", "chercher", "trouver", "produit", "article",
        "conseil", "suggestion", "idée", "idee", "tu me conseilles",
        "me conseiller", "me recommander", "tu proposes",
        "as tu", "avez vous", "je veux", "je voudrais",
    ]

    from .constants import PRODUCT_TYPE_KEYWORDS
    product_context_words = set()
    for kws in PRODUCT_TYPE_KEYWORDS.values():
        product_context_words.update(kws)
    product_context_words.update([s.lower() for s in CATEGORIES_SPORT])

    if re.search(r"(je cherche|je veux|j ai besoin|peux tu me trouver)", full_clean):
        return "conseil_produit"

    if any(w in full_clean for w in product_context_words):
        return "conseil_produit"

    if filtered_products:
        return "conseil_produit"

    if any(k in full_clean for k in keywords["taille"]):
        return "taille"

    if any(k in full_clean for k in keywords["disponibilite"]):
        return "disponibilite"

    if any(k in full_clean for k in keywords["prix"]):
        return "prix"

    if q in keywords["confirmation"]:
        past_intents = [
            m.get("intent")
            for m in conversation_history
            if m.get("role") == "assistant" and m.get("intent")
        ]
        if past_intents:
            last_intent = past_intents[-1]
            if last_intent in ("conseil_produit", "prix", "disponibilite", "taille"):
                return last_intent
        return "confirmation"

    if any(k in full_clean for k in conseil_keywords):
        return "conseil_produit"

    return "Autre"


@csrf_exempt
def chat_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Format JSON invalide"}, status=400)

    question = data.get("message", "").strip()
    if not question:
        return JsonResponse({"error": "Message vide"}, status=400)

    device = request.headers.get("User-Agent", "Inconnu")
    session_id = request.session.get("session_id")

    # Si aucune session "métier", on en crée une nouvelle et on remet à zéro les échanges
    if session_id:
        session = Session.objects.filter(id=session_id).first()
    else:
        user_id = str(uuid.uuid4())
        session = Session.objects.create(
            user_id=user_id,
            start_time=timezone.now(),
            device=device,
            location="Decathlon Lille Centre",
        )
        request.session["session_id"] = session.id
        request.session["user_id"] = user_id
        request.session["conversation_history"] = []
        request.session["questions_asked"] = 0

    conversation_history = request.session.get("conversation_history", [])
    questions_asked = request.session.get("questions_asked", 0)

    is_reset = data.get("reset", False)
    if is_reset:
        conversation_history = []
        questions_asked = 0
        request.session["conversation_history"] = []
        request.session["questions_asked"] = 0
        print("[RESET] Conversation réinitialisée")

    must_ask_questions = should_ask_questions(conversation_history)

    user_messages = [msg.get("content", "") for msg in conversation_history if msg.get("role") == "user"]
    user_messages.append(question)
    full_context = " ".join(user_messages)

    if must_ask_questions:
        print("[MODE] QUESTIONNEMENT - Pas de recherche")
        retrieved_products = []
        filtered_products = []
        intent = "questionnement"
    else:
        print("[MODE] RECOMMANDATION - Recherche activée")

        try:
            sport = extract_sport_category_from_query(full_context)
            product_type = infer_product_type_from_query(full_context)

            search_query_parts = []

            if product_type:
                search_query_parts.append(product_type)
                print(f"[SEARCH] Type de produit: {product_type}")

            if sport:
                search_query_parts.append(sport)
                print(f"[SEARCH] Sport: {sport}")

            if search_query_parts:
                search_query = " ".join(search_query_parts) + " " + full_context
            else:
                search_query = full_context

            print(f"[SEARCH] Requête: {search_query[:120]}...")

            retrieved_products = search_products(search_query, k=15000)

            for p in retrieved_products:
                p["score"] = compute_score(search_query, p)

            retrieved_products = sorted(retrieved_products, key=lambda x: x["score"], reverse=True)
            print(f"[VECTOR] {len(retrieved_products)} produits récupérés (brut).")
        except Exception as e:
            print(f"[VECTOR][ERREUR] {e}")
            retrieved_products = []

        filtered_products = filter_products_for_query(full_context, retrieved_products)
        print(f"[FILTER] {len(filtered_products)} produits après filtrage logique.")

        intent = infer_intent(question, conversation_history, filtered_products)

    print(f"[INTENT] Intent détecté : {intent}")

    start_time = timezone.now()

    try:
        answer, recommendations = call_deepseek(
            question=question,
            conversation_history=conversation_history,
            filtered_products=filtered_products,
            must_ask_questions=must_ask_questions,
            intent=intent
        )

        success = bool(answer and "erreur" not in answer.lower())

        conversation_history.append({"role": "user", "content": question})
        conversation_history.append({"role": "assistant", "content": answer})

        if "?" in answer and not recommendations:
            questions_asked += 1

        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]

        request.session["conversation_history"] = conversation_history
        request.session["questions_asked"] = questions_asked

    except Exception as e:
        answer = f"(Erreur DeepSeek : {str(e)})"
        success = False
        recommendations = []

    end_time = timezone.now()
    response_time = round((end_time - start_time).total_seconds(), 2)

    ask_feedback = False
    if intent in ["prix", "disponibilite", "taille"] or not success:
        ask_feedback = True
    elif intent == "conseil_produit" and recommendations:
        ask_feedback = True

    interaction = ChatbotInteraction.objects.create(
        session=session,
        question=question,
        response=answer,
        model_used="DeepSeek",
        intent=intent,
        response_time=response_time,
        response_success=success,
        ask_feedback=ask_feedback,
    )

    produits_json = []

    for rec in recommendations:
        produit = None

        vec_product = match_rec_to_vector_product(rec, filtered_products)
        if vec_product:
            ref = str(vec_product["reference"]).strip()
            produit = Product.objects.filter(product_id=ref).first()
            if produit:
                print(f"Produit trouvé via vector_store : {produit.name} (ref {produit.product_id})")
            else:
                print(f"Ref {ref} issue du vector_store introuvable en BDD, on tente la suite.")

        if not produit and rec.get("reference"):
            ref_llm = rec["reference"].strip()
            produit = Product.objects.filter(product_id=ref_llm).first()
            if produit:
                print(f"Produit trouvé par référence LLM : {produit.name} (ref {ref_llm})")

        if not produit and rec.get("nom"):
            produit = find_best_product(rec["nom"])
            if produit:
                print(f"Produit trouvé par nom global : {produit.name}")

        if produit:
            ChatbotRecommendation.objects.create(
                session=session,
                interaction=interaction,
                product=produit,
                recommended_at=timezone.now(),
            )
            print(f"Recommandation enregistrée en BD : {produit.name}")

            # Phrase d’introduction (bandeau au-dessus de la carte)
            description = rec.get("intro", "")
            if not description:
                description = f"Je vous recommande ce produit {produit.name}."

            # Description produit : uniquement la description BDD
            if produit.description:
                features_list = [produit.description]
            else:
                features_list = []

            produits_json.append({
                "id": produit.id,
                "reference": produit.product_id,
                "conversationId": interaction.id,
                "product": produit.name,
                "name": produit.name,
                "brand": produit.brand or "Décathlon",
                "price": f"{produit.price:.2f} €" if produit.price is not None else "",
                "category": produit.category or "",
                "sport": produit.sport or "",
                "imageUrl": produit.image_url or "",
                "image_url": produit.image_url or "",
                "imageUrlAlt": produit.image_url_alt or "",
                # Texte d’intro (Je vous recommande / N’oubliez pas…)
                "description": description,
                # Copie brute de la description BDD
                "productDescription": produit.description or "",
                # Description affichée dans la carte : EXACTEMENT celle de la BDD
                "features": features_list,
            })

            print(f"Produit ajouté au JSON : {produit.name} (ID: {produit.id})")
        else:
            print(f"Produit non trouvé : {rec.get('nom', 'N/A')} (ref: {rec.get('reference', 'N/A')})")

    print(f"Total produits recommandés : {len(produits_json)}")
    print(f"Total enregistrements en BD : {ChatbotRecommendation.objects.filter(interaction=interaction).count()}")

    return JsonResponse({
        "status": "success",
        "message": answer,
        "response": answer,
        "interaction_id": interaction.id,
        "session_id": session.id,
        "conversation_id": interaction.id,
        "intent": intent,
        "response_time": response_time,
        "ask_feedback": ask_feedback,
        "questions_asked": questions_asked,
        "recommendations": produits_json,
        "product_count": len(produits_json),
    })


@csrf_exempt
def feedback_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Format JSON invalide"}, status=400)

    interaction_id = data.get("interaction_id") or data.get("message_id")
    satisfaction_value = data.get("satisfaction")

    if interaction_id is None or satisfaction_value is None:
        return JsonResponse({"error": "Données manquantes"}, status=400)

    if isinstance(satisfaction_value, str):
        satisfaction_value = satisfaction_value.strip().lower()
        if satisfaction_value in ["oui", "yes", "true", "1"]:
            satisfaction_value = True
        elif satisfaction_value in ["non", "no", "false", "0"]:
            satisfaction_value = False
        else:
            return JsonResponse({"error": "Valeur invalide"}, status=400)
    elif not isinstance(satisfaction_value, bool):
        return JsonResponse({"error": "Valeur invalide"}, status=400)

    try:
        interaction = ChatbotInteraction.objects.get(id=interaction_id)
        interaction.satisfaction = satisfaction_value
        interaction.save(update_fields=["satisfaction"])

        return JsonResponse({
            "success": True,
            "message": "Satisfaction enregistrée",
            "interaction_id": interaction.id,
            "satisfaction": satisfaction_value,
        })
    except ChatbotInteraction.DoesNotExist:
        return JsonResponse({"error": "Interaction non trouvée"}, status=404)


@csrf_exempt
def reset_chat(request):
    try:
        session_id = request.session.get("session_id")

        if session_id:
            session = Session.objects.filter(id=session_id).first()
            if session:
                session.end_time = timezone.now()
                session.duration = session.end_time - session.start_time
                session.save()
                print(f"[SESSION] Session terminée : {session.id}")

        # On clôture complètement la session Django
        request.session["conversation_history"] = []
        request.session["questions_asked"] = 0
        request.session.flush()

        return JsonResponse({"success": True, "message": "Session clôturée."})

    except Exception as e:
        print(f"[ERREUR] reset_chat : {e}")
        return JsonResponse({"error": "Erreur lors de la réinitialisation"}, status=500)
