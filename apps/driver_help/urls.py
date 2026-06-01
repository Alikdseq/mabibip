from django.urls import path

from . import views

app_name = "driver_help"

urlpatterns = [
    path("", views.help_feed, name="feed"),
    path("create/", views.help_create, name="create"),
    path("<int:pk>/resolve/", views.help_resolve, name="resolve"),
    path("api/active-count/", views.help_active_count_api, name="active_count"),
]
