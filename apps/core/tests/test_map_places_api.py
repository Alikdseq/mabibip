import pytest
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse

from apps.classifieds.models import AutoShopProfile
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import CarBrand, ServiceSection, ServiceStation
from apps.users.models import User


@pytest.mark.django_db
def test_map_places_api_disabled_returns_503(client):
    url = reverse("api_map_places")
    r = client.get(url, {"bbox": "44.60,43.00,44.80,43.10"})
    assert r.status_code == 503


@pytest.mark.django_db
@override_settings(MAP_FEATURE_ENABLED=True)
def test_map_places_api_returns_sto_master_and_autoshop(client):
    owner = User.objects.create_user(phone="+79990001122", password="x")
    brand = CarBrand.objects.create(name="TestBrand", slug="testbrand", sprite_key="tb", is_popular=False, sort_order=0)
    sec = ServiceSection.objects.create(name="Подвеска", slug="susp", sort_order=10)

    sto = ServiceStation.objects.create(
        owner=owner,
        name="СТО Карта",
        slug="sto-map",
        address="ул. 1",
        location=Point(44.68, 43.05, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        executor_kind="sto",
    )
    sto.car_brands.add(brand)
    sto.service_sections.add(sec)

    master = ServiceStation.objects.create(
        owner=owner,
        parent_station=sto,
        name="Мастер Карта",
        slug="master-map",
        address="ул. 1",
        location=Point(44.681, 43.051, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        executor_kind="private",
    )
    master.car_brands.add(brand)
    master.service_sections.add(sec)

    shop = AutoShopProfile.objects.create(
        owner=owner,
        name="Магазин Карта",
        slug="shop-map",
        city_label="Владикавказ",
        address="ул. 2",
        location=Point(44.682, 43.052, srid=4326),
    )

    url = reverse("api_map_places")
    bbox = "44.60,43.00,44.80,43.10"
    r = client.get(url, {"bbox": bbox})
    assert r.status_code == 200
    types = {x["type"] for x in r.json()["results"]}
    assert {"sto", "master", "autoshop"} <= types


@pytest.mark.django_db
@override_settings(MAP_FEATURE_ENABLED=True)
def test_map_places_filters_by_brand_and_section(client):
    owner = User.objects.create_user(phone="+79990002233", password="x")
    brand_a = CarBrand.objects.create(name="A", slug="a", sprite_key="a", is_popular=False, sort_order=0)
    brand_b = CarBrand.objects.create(name="B", slug="b", sprite_key="b", is_popular=False, sort_order=0)
    sec_a = ServiceSection.objects.create(name="Asec", slug="asec", sort_order=10)
    sec_b = ServiceSection.objects.create(name="Bsec", slug="bsec", sort_order=10)

    s1 = ServiceStation.objects.create(
        owner=owner,
        name="S1",
        slug="s1",
        address="x",
        location=Point(44.70, 43.05, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        executor_kind="sto",
    )
    s1.car_brands.add(brand_a)
    s1.service_sections.add(sec_a)

    s2 = ServiceStation.objects.create(
        owner=owner,
        name="S2",
        slug="s2",
        address="x",
        location=Point(44.71, 43.05, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        executor_kind="sto",
    )
    s2.car_brands.add(brand_b)
    s2.service_sections.add(sec_b)

    url = reverse("api_map_places")
    bbox = "44.60,43.00,44.80,43.10"
    r = client.get(url, {"bbox": bbox, "brand": "a", "section": "asec", "types": "sto"})
    assert r.status_code == 200
    labels = {x["label"] for x in r.json()["results"]}
    assert "S1" in labels
    assert "S2" not in labels


@pytest.mark.django_db
@override_settings(MAP_FEATURE_ENABLED=True)
def test_map_places_filters_by_service_slug(client):
    owner = User.objects.create_user(phone="+79990003344", password="x")
    from apps.stations.models import ServiceCategory

    cat, _ = ServiceCategory.objects.get_or_create(name="Диагностика", defaults={"slug": "diag"})
    if cat.slug != "diag":
        # slug уникален; в тестовой базе мог существовать другой слаг
        cat.slug = "diag"
        cat.save(update_fields=["slug"])
    st = ServiceStation.objects.create(
        owner=owner,
        name="SVC",
        slug="svc",
        address="x",
        location=Point(44.70, 43.05, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        executor_kind="sto",
    )
    st.categories.add(cat)

    url = reverse("api_map_places")
    bbox = "44.60,43.00,44.80,43.10"
    r = client.get(url, {"bbox": bbox, "service": "diag", "types": "sto"})
    assert r.status_code == 200
    labels = {x["label"] for x in r.json()["results"]}
    assert "SVC" in labels

