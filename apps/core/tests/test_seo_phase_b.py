"""Фаза B SEO: meta description, OG, JSON-LD @graph (docs/seo/plan.md)."""

import json

import pytest
from django.test.utils import override_settings
from django.urls import reverse

from apps.stations.models import CarBrand, ServiceCategory, ServiceStation
from apps.users.models import User

pytestmark = pytest.mark.django_db(databases=["default"])


@override_settings(SITE_BASE_URL="")
def test_home_has_meta_description_and_og(client):
    r = client.get(reverse("home"))
    assert r.status_code == 200
    body = r.content.decode()
    assert '<meta name="description"' in body
    assert 'property="og:title"' in body
    assert 'property="og:url"' in body
    assert 'property="og:image"' in body
    assert "twitter:card" in body


@override_settings(SITE_BASE_URL="")
def test_catalog_has_unique_meta_and_title(client):
    owner = User.objects.create_user(phone="+79991110001", password="x")
    brand = CarBrand.objects.create(name="ToyotaTestSEO", slug="toyota-test-seo", sort_order=1)
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО SEO Каталог",
        slug="sto-seo-catalog",
        address="ул. SEO, 1",
        is_active=True,
        subscription_plan="free",
    )
    st.car_brands.add(brand)
    cat = ServiceCategory.objects.create(name="ШиномонтажSEO", slug="shina-seo-test")
    st.categories.add(cat)

    r = client.get(reverse("stations:list"), {"brand": "toyota-test-seo", "city": "Тестград"})
    assert r.status_code == 200
    body = r.content.decode()
    assert "ToyotaTestSEO" in body
    assert '<meta name="description"' in body
    assert 'property="og:description"' in body


@override_settings(SITE_BASE_URL="http://testserver")
def test_station_detail_json_ld_graph_and_telephone(client):
    owner = User.objects.create_user(phone="+79991110002", password="x")
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО JSON-LD",
        slug="sto-jsonld-seo",
        address="ул. Схемы, 1",
        is_active=True,
        subscription_plan="free",
        contact_phone="+79991234567",
        work_schedule_text="Пн–Пт 9:00–18:00",
        description_short="Диагностика и ремонт.",
    )
    r = client.get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert 'application/ld+json' in body
    # Вырезаем первый блок JSON-LD
    start = body.find('application/ld+json">') + len('application/ld+json">')
    end = body.find("</script>", start)
    raw = body[start:end].strip()
    data = json.loads(raw)
    assert "@graph" in data
    types = {n.get("@type") for n in data["@graph"]}
    assert "BreadcrumbList" in types
    assert "AutoRepair" in types
    entity = next(x for x in data["@graph"] if x.get("@type") == "AutoRepair")
    assert entity.get("telephone") == "+79991234567"
    assert "Диагностика" in (entity.get("description") or "")
