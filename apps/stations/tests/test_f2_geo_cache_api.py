"""Фаза F2: геопоиск, кэш карточки, API nearby (PLAN-FULL-TZ-ATOMIC)."""

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.stations.card_cache import get_station_card_cache, set_station_card_cache
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79995550101",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


def _visible_station(owner, *, slug: str, lng: float, lat: float):
    return ServiceStation.objects.create(
        owner=owner,
        name=f"СТО {slug}",
        slug=slug,
        address="ул. Тестовая, 1",
        location=Point(lng, lat, srid=4326),
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        subscription_paid_until=None,
        is_active=True,
    )


@pytest.mark.django_db
def test_f2_t1_nearby_in_radius_only(owner):
    """F2.T1: станция в радиусе попадает; вне — нет."""
    # Две точки на одном меридиане: ~24 км друг от друга (лимит API radius_km ≤ 100).
    near = _visible_station(owner, slug="near", lng=37.62, lat=55.75)
    far = _visible_station(owner, slug="far", lng=37.62, lat=55.97)

    today = timezone.localdate()
    assert near in ServiceStation.objects.visible_in_catalog(today=today)

    client = APIClient()
    url = reverse("api_stations_nearby")
    r = client.get(url, {"lat": "55.75", "lng": "37.62", "radius_km": "30"})
    assert r.status_code == 200
    ids = {row["id"] for row in r.data["results"]}
    assert near.pk in ids
    assert far.pk in ids

    r2 = client.get(url, {"lat": "55.75", "lng": "37.62", "radius_km": "15"})
    assert r2.status_code == 200
    ids2 = {row["id"] for row in r2.data["results"]}
    assert near.pk in ids2
    assert far.pk not in ids2


@pytest.mark.django_db
def test_f2_t2_cache_invalidated_on_name_change(owner):
    """F2.T2: инвалидация кэша при смене названия."""
    st = _visible_station(owner, slug="cache-me", lng=37.6, lat=55.7)
    set_station_card_cache(
        st.pk,
        {"name": st.name, "slug": st.slug, "avg_rating": None},
    )
    assert get_station_card_cache(st.pk) is not None

    st.name = "Новое имя СТО"
    st.save()
    assert get_station_card_cache(st.pk) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [
        {"lat": "91", "lng": "0"},
        {"lat": "0", "lng": "200"},
        {"lat": "-91", "lng": "0"},
    ],
)
def test_f2_t3_lat_lng_out_of_range_400(owner, params):
    """F2.T3: lat/lng вне диапазона — 400."""
    _visible_station(owner, slug="x", lng=37.0, lat=55.0)
    client = APIClient()
    r = client.get(reverse("api_stations_nearby"), {**params, "radius_km": "5"})
    assert r.status_code == 400
