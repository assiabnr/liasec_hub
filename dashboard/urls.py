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
    path("", views.dashboard_home, name="dashboard_home"),
    path("chart-data/", views.chart_data, name="chart_data"),

    # Sessions
    path("sessions/", views.sessions_view, name="sessions"),
    path("sessions/analytics-data/", sessions_analytics_data, name="sessions_analytics_data"),
    path("session/<int:session_id>/detail/", session_detail_view, name="session_detail"),

    # Clics
    path("clicks/", views.clicks_view, name="clicks"),
    path("clicks/chart-data/", clicks_chart_data, name="clicks_chart_data"),

    # Produits
    path("produits/", views.produits_view, name="produits"),
    path("produits/<int:product_id>/", product_detail_view, name="product_detail"),
    path("produits/chart-data/", products_chart_data, name="products_chart_data"),

    # Analyse des interactions chatbot (statistiques uniquement)
    path("chatbot/", views.chatbot_view, name="chatbot"),
    path("chatbot/chart-data/", chatbot_chart_data, name="chatbot_chart_data"),
    path("chatbot/analytics-data/", chatbot_analytics_data, name="chatbot_analytics_data"),

    # API détails chatbot
    path("chatbot/question-detail/", chatbot_question_detail, name="chatbot_question_detail"),
    path("chatbot/session-detail/<int:session_id>/", chatbot_session_detail_api, name="chatbot_session_detail_api"),
    path("chatbot/intent-detail/", chatbot_intent_detail, name="chatbot_intent_detail"),
    path("chatbot/product-detail/<int:product_id>/", chatbot_product_detail_api, name="chatbot_product_detail_api"),
    path("chatbot/interaction-detail/<int:interaction_id>/", chatbot_interaction_detail_api, name="chatbot_interaction_detail_api"),

    # Paramètres
    path("settings/", views.settings_view, name="settings"),
    path("reset/", views.reset_data_view, name="reset_data"),

    # Exports
    path("export-history/", views.export_history_view, name="export_history"),
    path("exports/", views.exports_view, name="exports"),
    path("export-data/", views.export_data_view, name="export_data"),

    # Exports PDF
    path("export-pdf/dashboard/", views.export_dashboard_pdf, name="export_dashboard_pdf"),
    path("export-pdf/sessions/", views.export_sessions_pdf, name="export_sessions_pdf"),
    path("export-pdf/chatbot/", views.export_chatbot_pdf, name="export_chatbot_pdf"),
    path("export-pdf/produits/", views.export_products_pdf, name="export_products_pdf"),
    path("export-pdf/clicks/", views.export_clicks_pdf, name="export_clicks_pdf"),

    # Gestion des utilisateurs
    path("users/", views.users_management, name="users_management"),

    # Notifications
    path("notifications/", views.notifications_page, name="notifications"),
    path("api/notifications/", views.get_notifications_api, name="get_notifications_api"),
    path("api/notifications/<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("api/notifications/read-all/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("api/notifications/<int:notification_id>/delete/", views.delete_notification, name="delete_notification"),
]
