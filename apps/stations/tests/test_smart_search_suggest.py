"""API умных подсказок и словаря фраз."""

import pytest
from django.urls import reverse

from apps.stations.models import ServiceCategory, ServiceSearchPhrase, ServiceSection, ServiceStation
from apps.users.models import User


@pytest.mark.django_db
def test_suggest_uses_search_phrase_and_returns_service_url(client):
    owner = User.objects.create_user(phone="+79991110011", password="x")
    cat, _ = ServiceCategory.objects.get_or_create(
        slug="komp-diagnostika",
        defaults={"name": "Компьютерная диагностика"},
    )
    ServiceSearchPhrase.objects.create(phrase="троит двигатель", category=cat, weight=9)
    ServiceStation.objects.create(
        owner=owner,
        name="СТО Альфа",
        slug="sto-alfa",
        address="ул. 1",
        is_active=True,
        subscription_plan="free",
    )

    r = client.get(reverse("api_search_suggest"), {"q": "троит"})
    assert r.status_code == 200
    data = r.json()
    assert data["services"]
    assert any(s["slug"] == cat.slug for s in data["services"])
    svc_row = next(s for s in data["results"] if s["type"] == "category")
    assert f"/uslugi/{cat.slug}/" in svc_row["url"]


@pytest.mark.django_db
def test_suggest_matches_colloquial_engine_knock_and_squeak(client):
    """«Двигатель стучит» ↔ словарная «стук в двигателе»; «скрипит» ↔ «скрип в подвеске»."""
    owner = User.objects.create_user(phone="+79991110099", password="x")
    cat_engine, _ = ServiceCategory.objects.get_or_create(name="Дефектовка ДВС", slug="defektovka-dvs")
    cat_susp, _ = ServiceCategory.objects.get_or_create(name="Замена сайлентблоков", slug="zamena-silent")
    ServiceSearchPhrase.objects.create(phrase="стук в двигателе", category=cat_engine, weight=8)
    ServiceSearchPhrase.objects.create(phrase="скрип в подвеске", category=cat_susp, weight=8)
    ServiceStation.objects.create(
        owner=owner,
        name="СТО Тест",
        slug="sto-test-col",
        address="ул. 9",
        is_active=True,
        subscription_plan="free",
    )

    r1 = client.get(reverse("api_search_suggest"), {"q": "двигатель стучит", "services_only": "1"})
    assert r1.status_code == 200
    slugs1 = [s["slug"] for s in r1.json()["services"]]
    assert "defektovka-dvs" in slugs1

    r2 = client.get(reverse("api_search_suggest"), {"q": "скрипит", "services_only": "1"})
    assert r2.status_code == 200
    slugs2 = [s["slug"] for s in r2.json()["services"]]
    assert "zamena-silent" in slugs2


@pytest.mark.django_db
def test_catalog_applies_service_slug_filter(client):
    owner = User.objects.create_user(phone="+79992220022", password="x")
    cat, _ = ServiceCategory.objects.get_or_create(name="Тестовая услуга", slug="testovaya-usluga")
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО Бета",
        slug="sto-beta",
        address="ул. 2",
        is_active=True,
        subscription_plan="free",
    )
    st.categories.add(cat)
    ServiceStation.objects.create(
        owner=owner,
        name="СТО Гамма",
        slug="sto-gamma",
        address="ул. 3",
        is_active=True,
        subscription_plan="free",
    )

    r = client.get(reverse("stations:list"), {"cat": str(cat.pk)})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert "sto-beta" in slugs
    assert "sto-gamma" not in slugs


@pytest.mark.django_db
def test_suggest_returns_sections_and_masters(client):
    owner = User.objects.create_user(phone="+79993330033", password="x")
    sec = ServiceSection.objects.create(name="Двигатель", slug="dvigatel", sort_order=1)
    ServiceCategory.objects.get_or_create(name="Замена масла", slug="zamena-masla", defaults={})
    sto = ServiceStation.objects.create(
        owner=owner,
        name="СТО Омега",
        slug="sto-omega",
        address="ул. 5",
        is_active=True,
        subscription_plan="free",
    )
    master = ServiceStation.objects.create(
        owner=owner,
        parent_station=sto,
        name="Мастер Иван",
        slug="master-ivan",
        address="ул. 5",
        tagline="Диагностика двигателя",
        is_active=True,
        subscription_plan="free",
    )

    r = client.get(reverse("api_search_suggest"), {"q": "двиг", "limit_sections": "5", "limit_masters": "5"})
    assert r.status_code == 200
    data = r.json()
    assert any(x["type"] == "section" and x["slug"] == sec.slug for x in data["results"])
    assert any(x["type"] == "master" and x["slug"] == master.slug for x in data["results"])
