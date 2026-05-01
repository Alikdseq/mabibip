"""Фаза C: ЧПУ /uslugi/, /marki/, редирект с ?service= (docs/seo/plan.md)."""

import pytest
from django.urls import reverse

from apps.stations.models import CarBrand, ServiceCategory, ServiceStation
from apps.users.models import User
from apps.core.visitor_city import SESSION_KEY as VISITOR_CITY_SESSION_KEY

pytestmark = pytest.mark.django_db(databases=["default"])


def test_catalog_redirects_service_only_to_landing(client):
    owner = User.objects.create_user(phone="+79993330001", password="x")
    cat, _ = ServiceCategory.objects.get_or_create(
        slug="usluga-redir-test",
        defaults={"name": "Услуга редирект тест"},
    )
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО Редирект",
        slug="sto-redir-test",
        address="ул. Р, 1",
        is_active=True,
        subscription_plan="free",
    )
    st.categories.add(cat)

    r = client.get(reverse("stations:list"), {"service": "usluga-redir-test"}, follow=False)
    assert r.status_code == 301
    assert r["Location"].endswith(f"/uslugi/usluga-redir-test/")


def test_catalog_no_redirect_when_brand_with_service(client):
    owner = User.objects.create_user(phone="+79993330002", password="x")
    cat, _ = ServiceCategory.objects.get_or_create(slug="u2", defaults={"name": "U2"})
    ServiceStation.objects.create(
        owner=owner,
        name="СТО2",
        slug="sto2",
        address="ул. 2",
        is_active=True,
        subscription_plan="free",
    )
    r = client.get(reverse("stations:list"), {"service": "u2", "brand": "toyota"}, follow=False)
    assert r.status_code == 200


def test_service_landing_renders(client):
    owner = User.objects.create_user(phone="+79993330003", password="x")
    brand = CarBrand.objects.create(name="BrandForService", slug="brand-for-service", sort_order=1)
    cat = ServiceCategory.objects.create(
        name="Лендинг SEO",
        slug="landing-seo-cat",
        landing_lead="Уникальный лид для теста лендинга.",
        landing_faq=[
            {"q": "Вопрос один?", "a": "Ответ один."},
            {"q": "Вопрос два?", "a": "Ответ два."},
        ],
    )
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО для услуги",
        slug="sto-for-service",
        address="ул. Тест, 1",
        is_active=True,
        subscription_plan="free",
    )
    st.categories.add(cat)
    st.car_brands.add(brand)
    session = client.session
    if VISITOR_CITY_SESSION_KEY in session:
        del session[VISITOR_CITY_SESSION_KEY]
        session.save()
    r = client.get(reverse("landing:service_category", kwargs={"slug": "landing-seo-cat"}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Лендинг SEO" in body
    assert "Уникальный лид для теста лендинга." in body
    assert "Частые вопросы" in body
    assert "Вопрос один?" in body
    assert "FAQPage" in body
    assert "Выберите марку авто" in body
    assert "/sto/?service=landing-seo-cat" in body
    assert "brand=" in body
    assert 'rel="canonical"' in body


def test_brand_landing_renders(client):
    CarBrand.objects.create(name="BrandSEO", slug="brand-seo-c", sort_order=1)
    r = client.get(reverse("landing:car_brand", kwargs={"slug": "brand-seo-c"}))
    assert r.status_code == 200
    assert "BrandSEO" in r.content.decode()
