from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    # === Pages principales ===
    path("", views.index_view, name="chatbot_index"),
    path("tos/", views.tos_view, name="chatbot_tos"),
    path("accept_tos/", views.accept_tos, name="accept_tos"),
    path("chat/", views.chat_view, name="chatbot_chat"),

    # === API du chatbot ===
    path("api/ask/", views.chat_api, name="chat_api"),
    path("api/feedback/", views.feedback_api, name="feedback_api"),
    path("api/reset/", views.reset_chat, name="reset_chat"),
]
