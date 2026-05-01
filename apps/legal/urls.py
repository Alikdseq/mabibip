from django.urls import path

from . import views

app_name = "legal"

urlpatterns = [
    path("", views.LegalArchiveView.as_view(), name="archive"),
    path("sto/consent/", views.StoConsentView.as_view(), name="sto_consent"),
    path("<str:key>/", views.LegalDocumentCurrentView.as_view(), name="document"),
]
