from django.urls import path
from . import views, views_admin

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("force-change-password/", views.force_change_password, name="force_change_password"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.reset_password_confirm, name="password_reset_confirm"),
path("api/users/", views_admin.users_list_create, name="users_list_create"),
    path("api/users/<int:user_id>/", views.user_detail, name="user_detail"),
]
