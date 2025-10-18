from django.urls import path
from . import views
from .views import session_detail_view, clicks_chart_data, products_chart_data, chatbot_chart_data

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('chart-data/', views.chart_data, name='chart_data'),
    path('sessions/', views.sessions_view, name='sessions'),
    path("session/<int:session_id>/detail/", session_detail_view, name="session_detail"),
    path('clicks/', views.clicks_view, name='clicks'),
    path("clicks/chart-data/", clicks_chart_data, name="clicks_chart_data"),
    path('produits/', views.produits_view, name='produits'),
    path("produits/chart-data/", products_chart_data, name="products_chart_data"),
    path('chatbot/', views.chatbot_view, name='chatbot'),
    path("chatbot/chart-data/", chatbot_chart_data, name="chatbot_chart_data"),
    path('settings/', views.settings_view, name='settings'),
    path("reset/", views.reset_data_view, name="reset_data"),
    path("export-history/", views.export_history_view, name="export_history"),
    path('exports/', views.exports_view, name='exports'),
    path("export-data/", views.export_data_view, name="export_data"),
    path("users/", views.users_management, name="users_management"),
]
