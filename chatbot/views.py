import json
import uuid
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from mistralai import Mistral
from dashboard.models import Session, ChatbotInteraction


# =========================================================
# INITIALISATION DU CLIENT MISTRAL
# =========================================================
try:
    client = Mistral(api_key=settings.MISTRAL_API_KEY)
except Exception as e:
    client = None
    print(f"[ERREUR] Impossible d’initialiser Mistral : {e}")


# =========================================================
# PAGES DU CHATBOT
# =========================================================
def index_view(request):
    """Page d’accueil du chatbot (écran d’attente)."""
    return render(request, "chatbot/index.html")


def tos_view(request):
    """Page des conditions d’utilisation."""
    return render(request, "chatbot/tos.html")


def chat_view(request):
    """Page principale du chatbot."""
    return render(request, "chatbot/chat.html")


# =========================================================
# ACCEPTATION DES TOS ET CRÉATION DE SESSION
# =========================================================
def accept_tos(request):
    """Crée une session dès que l’utilisateur accepte les TOS."""
    try:
        if request.method == "POST":
            user_id = str(uuid.uuid4())

            session = Session.objects.create(
                user_id=user_id,
                start_time=timezone.now(),
                device=request.META.get("HTTP_USER_AGENT", "inconnu"),
                location="Decathlon Lille Centre",
            )

            request.session["session_id"] = session.id
            request.session["user_id"] = user_id

            return redirect("chatbot:chatbot_chat")

        return render(request, "chatbot/tos.html")

    except Exception as e:
        print(f"[ERREUR] accept_tos : {e}")
        return render(request, "chatbot/tos.html", {
            "error_message": "Une erreur est survenue. Veuillez réessayer."
        })


# =========================================================
# API DE CONVERSATION AVEC MISTRAL
# =========================================================
@csrf_exempt
def chat_api(request):
    """API principale du chatbot — enregistre les interactions enrichies avec logique de feedback."""
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    # Lecture du message utilisateur
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Format JSON invalide"}, status=400)

    question = data.get("message", "").strip()
    if not question:
        return JsonResponse({"error": "Message vide"}, status=400)

    # Gestion session utilisateur
    device = request.headers.get("User-Agent", "Inconnu")
    session_id = request.session.get("session_id")
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

    # === Détection simple d’intention ===
    lower_q = question.lower()
    if any(k in lower_q for k in ["prix", "coût", "combien"]):
        intent = "prix"
    elif any(k in lower_q for k in ["dispo", "stock", "en vente", "encore disponible"]):
        intent = "disponibilite"
    elif any(k in lower_q for k in ["taille", "pointure", "format"]):
        intent = "taille"
    elif any(k in lower_q for k in ["recherche", "produit", "conseil", "idée"]):
        intent = "conseil_produit"
    else:
        intent = "Autre"

    # === Appel Mistral ===
    start_time = timezone.now()
    if not client:
        answer = f"[TEST] Vous avez dit : {question}"
        success = True
    else:
        try:
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": "Tu es un assistant Decathlon utile et précis."},
                    {"role": "user", "content": question},
                ],
            )
            answer = response.choices[0].message["content"].strip()
            success = bool(answer and "erreur" not in answer.lower())
        except Exception as e:
            answer = f"(Erreur Mistral : {str(e)})"
            success = False
    end_time = timezone.now()
    response_time = round((end_time - start_time).total_seconds(), 2)

    # === Logique d'affichage du feedback intelligent ===
    ask_feedback = False
    if intent in ["prix", "disponibilite", "taille"] or not success:
        ask_feedback = True
    elif intent == "conseil_produit":
        # On vérifie si c’est la 3ᵉ interaction ou plus dans ce contexte (dialogue complet)
        total_context = ChatbotInteraction.objects.filter(
            session=session, intent="conseil_produit"
        ).count()
        if total_context >= 3:
            ask_feedback = True

    # === Enregistrement enrichi ===
    interaction = ChatbotInteraction.objects.create(
        session=session,
        question=question,
        response=answer,
        model_used="Mistral" if client else "Test",
        intent=intent,
        response_time=response_time,
        response_success=success,
        ask_feedback=ask_feedback,
    )

    return JsonResponse({
        "response": answer,
        "interaction_id": interaction.id,
        "session_id": session.id,
        "intent": intent,
        "response_time": response_time,
        "ask_feedback": ask_feedback,
    })


# =========================================================
# API DE FEEDBACK UTILISATEUR
# =========================================================
@csrf_exempt
def feedback_api(request):
    """
    API pour enregistrer la satisfaction utilisateur (binaire Oui / Non).
    Accepte un JSON : { "interaction_id": 123, "satisfaction": true }.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    # Vérifie le format JSON
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Format JSON invalide"}, status=400)

    interaction_id = data.get("interaction_id")
    satisfaction_value = data.get("satisfaction")

    # Vérification des champs requis
    if interaction_id is None or satisfaction_value is None:
        return JsonResponse({"error": "Données manquantes"}, status=400)

    # Conversion et normalisation du feedback Oui/Non
    if isinstance(satisfaction_value, str):
        satisfaction_value = satisfaction_value.strip().lower()
        if satisfaction_value in ["oui", "yes", "true", "1"]:
            satisfaction_value = True
        elif satisfaction_value in ["non", "no", "false", "0"]:
            satisfaction_value = False
        else:
            return JsonResponse({"error": "Valeur de satisfaction invalide"}, status=400)

    elif not isinstance(satisfaction_value, bool):
        return JsonResponse({"error": "Valeur de satisfaction invalide"}, status=400)

    # Sauvegarde du feedback
    try:
        interaction = ChatbotInteraction.objects.get(id=interaction_id)
        interaction.satisfaction = satisfaction_value
        interaction.save(update_fields=["satisfaction"])
        return JsonResponse({
            "success": True,
            "message": "Satisfaction enregistrée",
            "interaction_id": interaction.id,
            "satisfaction": satisfaction_value
        })
    except ChatbotInteraction.DoesNotExist:
        return JsonResponse({"error": "Interaction non trouvée"}, status=404)
# =========================================================
# RESET DU CHAT
# =========================================================
@csrf_exempt
def reset_chat(request):
    """Clôture proprement la session active."""
    try:
        session_id = request.session.get("session_id")

        if session_id:
            session = Session.objects.filter(id=session_id).first()
            if session:
                session.end_time = timezone.now()
                session.duration = session.end_time - session.start_time
                session.save()
                print(f"[SESSION] Session terminée : {session.id}")

        request.session.flush()
        return JsonResponse({"success": True, "message": "Session clôturée."})

    except Exception as e:
        print(f"[ERREUR] reset_chat : {e}")
        return JsonResponse({"error": "Erreur lors de la réinitialisation"}, status=500)


def close_inactive_sessions():
    """Clôture automatiquement les sessions inactives depuis plus de 10 minutes."""
    threshold = timezone.now() - timezone.timedelta(minutes=10)
    inactive_sessions = Session.objects.filter(end_time__isnull=True, start_time__lt=threshold)
    for s in inactive_sessions:
        s.end_time = timezone.now()
        s.duration = s.end_time - s.start_time
        s.save()
