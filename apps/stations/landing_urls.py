"""ЧПУ-лендинги услуг и марок (фаза C)."""

from django.urls import path

from .landing import CarBrandLandingView, ServiceCategoryLandingView, ServiceSectionLandingView

app_name = "landing"

urlpatterns = [
    path("uslugi/<slug:slug>/", ServiceCategoryLandingView.as_view(), name="service_category"),
    path("marki/<slug:slug>/", CarBrandLandingView.as_view(), name="car_brand"),
    path("razdely/<slug:slug>/", ServiceSectionLandingView.as_view(), name="service_section"),
]
