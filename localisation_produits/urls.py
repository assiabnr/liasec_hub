from django.urls import path
from . import views

app_name = "localisation_produits"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/search/", views.search_products_api, name="search_api"),
    path("api/track-view/", views.track_product_view_api, name="track_view_api"),
    path("api/track-localization/", views.track_product_localization_api, name="track_localization_api"),
]