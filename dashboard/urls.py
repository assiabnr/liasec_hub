from django.urls import path
from django.contrib.auth.decorators import login_required
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
    path("", login_required(views.dashboard_home), name="dashboard_home"),
    path("chart-data/", login_required(views.chart_data), name="chart_data"),

    # Sessions
    path("sessions/", login_required(views.sessions_view), name="sessions"),
    path("sessions/analytics-data/", login_required(sessions_analytics_data), name="sessions_analytics_data"),
    path("session/<int:session_id>/detail/", login_required(session_detail_view), name="session_detail"),

    # Clics
    path("clicks/", login_required(views.clicks_view), name="clicks"),
    path("clicks/chart-data/", login_required(clicks_chart_data), name="clicks_chart_data"),

    # Produits
    path("produits/", login_required(views.produits_view), name="produits"),
    path("produits/<int:product_id>/", login_required(product_detail_view), name="product_detail"),
    path("produits/chart-data/", login_required(products_chart_data), name="products_chart_data"),

    # Analyse des interactions chatbot (statistiques uniquement)
    path("chatbot/", login_required(views.chatbot_view), name="chatbot"),
    path("chatbot/chart-data/", login_required(chatbot_chart_data), name="chatbot_chart_data"),
    path("chatbot/analytics-data/", login_required(chatbot_analytics_data), name="chatbot_analytics_data"),

    # API détails chatbot
    path("chatbot/question-detail/", login_required(chatbot_question_detail), name="chatbot_question_detail"),
    path("chatbot/session-detail/<int:session_id>/", login_required(chatbot_session_detail_api), name="chatbot_session_detail_api"),
    path("chatbot/intent-detail/", login_required(chatbot_intent_detail), name="chatbot_intent_detail"),
    path("chatbot/product-detail/<int:product_id>/", login_required(chatbot_product_detail_api), name="chatbot_product_detail_api"),
    path("chatbot/interaction-detail/<int:interaction_id>/", login_required(chatbot_interaction_detail_api), name="chatbot_interaction_detail_api"),

    # Paramètres
    path("settings/", login_required(views.settings_view), name="settings"),
    path("reset/", login_required(views.reset_data_view), name="reset_data"),

    # Exports
    path("export-history/", login_required(views.export_history_view), name="export_history"),
    path("exports/", login_required(views.exports_view), name="exports"),
    path("export-data/", login_required(views.export_data_view), name="export_data"),

    # Exports PDF
    path("export-pdf/dashboard/", login_required(views.export_dashboard_pdf), name="export_dashboard_pdf"),
    path("export-pdf/sessions/", login_required(views.export_sessions_pdf), name="export_sessions_pdf"),
    path("export-pdf/chatbot/", login_required(views.export_chatbot_pdf), name="export_chatbot_pdf"),
    path("export-pdf/produits/", login_required(views.export_products_pdf), name="export_products_pdf"),
    path("export-pdf/clicks/", login_required(views.export_clicks_pdf), name="export_clicks_pdf"),

    # Gestion des utilisateurs
    path("users/", login_required(views.users_management), name="users_management"),

    # Notifications
    path("notifications/", login_required(views.notifications_page), name="notifications"),
    path("api/notifications/", login_required(views.get_notifications_api), name="get_notifications_api"),
    path("api/notifications/<int:notification_id>/read/", login_required(views.mark_notification_read), name="mark_notification_read"),
    path("api/notifications/read-all/", login_required(views.mark_all_notifications_read), name="mark_all_notifications_read"),
    path("api/notifications/<int:notification_id>/delete/", login_required(views.delete_notification), name="delete_notification"),
]
