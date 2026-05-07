import pytest
from django.urls import reverse

from apps.stations.models import CarBrand, ServiceCategory, ServiceSection


pytestmark = pytest.mark.django_db


def test_category_landing_has_breadcrumb_jsonld(client):
    cat = ServiceCategory.objects.create(name="Замена масла", slug="oil")
    r = client.get(reverse("landing:service_category", kwargs={"slug": cat.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "BreadcrumbList" in body


def test_section_landing_has_breadcrumb_jsonld(client):
    sec = ServiceSection.objects.create(name="Техобслуживание", slug="service")
    r = client.get(reverse("landing:service_section", kwargs={"slug": sec.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "BreadcrumbList" in body


def test_brand_landing_has_breadcrumb_jsonld(client):
    brand = CarBrand.objects.create(name="BMW", slug="bmw")
    r = client.get(reverse("landing:car_brand", kwargs={"slug": brand.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "BreadcrumbList" in body

