import uuid
from django.utils import timezone
from dashboard.models import Session


def get_or_create_session(request):
    session_id = request.session.get("session_id")
    session = None

    if session_id:
        session = Session.objects.filter(id=session_id).first()

    if not session:
        session = Session.objects.create(
            session_id=str(uuid.uuid4()),
            start_time=timezone.now()
        )
        request.session["session_id"] = session.id
        print(f"[SESSION] Nouvelle session créée : {session.id}")
    else:
        print(f"[SESSION] Session existante : {session.id}")

    return session


def close_session(request):
    session_id = request.session.get("session_id")

    if session_id:
        session = Session.objects.filter(id=session_id).first()
        if session:
            session.end_time = timezone.now()
            session.duration = session.end_time - session.start_time
            session.save()
            print(f"[SESSION] Session terminée : {session.id}")

    request.session["conversation_history"] = []
    request.session["questions_asked"] = 0
    request.session.flush()


def get_conversation_history(request):
    return request.session.get("conversation_history", [])


def get_questions_asked(request):
    return request.session.get("questions_asked", 0)


def update_conversation_history(request, question, answer, questions_asked):
    conversation_history = get_conversation_history(request)

    conversation_history.append({"role": "user", "content": question})
    conversation_history.append({"role": "assistant", "content": answer})

    if "?" in answer:
        questions_asked += 1

    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    request.session["conversation_history"] = conversation_history
    request.session["questions_asked"] = questions_asked

    return conversation_history, questions_asked