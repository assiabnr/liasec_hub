from django.urls import path
from . import views
from .views import (
    session_detail_view,
    sessions_analytics_data,
    clicks_chart_data,
    products_chart_data,
    product_detail_view,
    chatbot_chart_data,
    chatbot_analytics_data,
    chatbot_question_detail,
    chatbot_session_detail_api,
    chatbot_intent_detail,
    chatbot_product_detail_api,
    chatbot_interaction_detail_api,
)

urlpatterns = [
    # Tableau de bord principal
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path("dashboard/chart-data/", views.chart_data, name="chart_data"),

    # Sessions
    path("dashboard/sessions/", views.sessions_view, name="sessions"),
    path("dashboard/sessions/analytics-data/", sessions_analytics_data, name="sessions_analytics_data"),
    path("session/<int:session_id>/detail/", session_detail_view, name="session_detail"),

    # Clics
    path("dashboard/clicks/", views.clicks_view, name="clicks"),
    path("dashboard/clicks/chart-data/", clicks_chart_data, name="clicks_chart_data"),

    # Produits
    path("dashboard/produits/", views.produits_view, name="produits"),
    path("dashboard/produits/<int:product_id>/", product_detail_view, name="product_detail"),
    path("dashboard/produits/chart-data/", products_chart_data, name="products_chart_data"),

    # Analyse des interactions chatbot (statistiques uniquement)
    path("dashboard/chatbot/", views.chatbot_view, name="chatbot"),
    path("dashboard/chatbot/chart-data/", chatbot_chart_data, name="chatbot_chart_data"),
    path("dashboard/chatbot/analytics-data/", chatbot_analytics_data, name="chatbot_analytics_data"),

    # API détails chatbot
    path("dashboard/chatbot/question-detail/", chatbot_question_detail, name="chatbot_question_detail"),
    path("dashboard/chatbot/session-detail/<int:session_id>/", chatbot_session_detail_api, name="chatbot_session_detail_api"),
    path("dashboard/chatbot/intent-detail/", chatbot_intent_detail, name="chatbot_intent_detail"),
    path("dashboard/chatbot/product-detail/<int:product_id>/", chatbot_product_detail_api, name="chatbot_product_detail_api"),
    path("dashboard/chatbot/interaction-detail/<int:interaction_id>/", chatbot_interaction_detail_api, name="chatbot_interaction_detail_api"),

    # Paramètres
    path("dashboard/settings/", views.settings_view, name="settings"),
    path("dashboard/reset/", views.reset_data_view, name="reset_data"),

    # Exports
    path("dashboard/export-history/", views.export_history_view, name="export_history"),
    path("dashboard/exports/", views.exports_view, name="exports"),
    path("dashboard/export-data/", views.export_data_view, name="export_data"),

    # Gestion des utilisateurs
    path("dashboard/users/", views.users_management, name="users_management"),
]
