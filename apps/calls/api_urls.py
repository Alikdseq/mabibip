from django.urls import path

from . import api_views

app_name = "calls_api"

urlpatterns = [
    path("initiate/", api_views.CallsInitiateAPIView.as_view(), name="initiate"),
    path("action/", api_views.CallsActionAPIView.as_view(), name="action"),
]

