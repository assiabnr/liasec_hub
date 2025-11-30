
"""Domain-split views to keep this module lean."""
from .views_dashboard import dashboard_home, chart_data
from .views_sessions import (
    sessions_view,
    sessions_analytics_data,
    session_detail_view,
    delete_session_view,
)
from .views_clicks import clicks_view, clicks_chart_data
from .views_products import produits_view, product_detail_view, products_chart_data
from .views_chatbot import (
    chatbot_view,
    chatbot_analytics_data,
    chatbot_question_detail,
    chatbot_session_detail_api,
    chatbot_intent_detail,
    chatbot_product_detail_api,
    chatbot_interaction_detail_api,
    chatbot_chart_data,
)
from .views_settings import settings_view, reset_data_view
from .views_exports import (
    export_history_view,
    exports_view,
    export_data_view,
    grant_export_access,
    export_dashboard_pdf,
    export_sessions_pdf,
    export_chatbot_pdf,
    export_products_pdf,
    export_clicks_pdf,
)
from .views_users import users_management
from .views_notifications import (
    get_notifications_api,
    mark_notification_read,
    mark_all_notifications_read,
    delete_notification,
    notifications_page,
    get_notification_icon,
)
