from django.urls import path

from .api_views import AdReportAPIView, RevealPhoneAPIView

app_name = "classifieds_api"

urlpatterns = [
    path("ads/<int:pk>/reveal-phone/", RevealPhoneAPIView.as_view(), name="ad_reveal_phone"),
    path("ads/<int:pk>/report/", AdReportAPIView.as_view(), name="ad_report"),
]

