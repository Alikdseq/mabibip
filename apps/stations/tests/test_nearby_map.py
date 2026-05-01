"""Страница карты «СТО рядом»."""

import pytest
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.urls import reverse

from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation
from apps.users.models import User


@pytest.mark.django_db
def test_nearby_map_disabled_shows_stub(client):
    r = client.get(reverse("stations:nearby_map"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Режим карты временно отключён" in body


@pytest.mark.django_db
@override_settings(MAP_FEATURE_ENABLED=True)
def test_nearby_map_without_coords_renders(client):
    r = client.get(reverse("stations:nearby_map"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "nearby-map" in body


@pytest.mark.django_db
@override_settings(MAP_FEATURE_ENABLED=True)
def test_nearby_map_with_coords_lists_station(client):
    owner = User.objects.create_user(phone="+79993331122", password="x")
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО Гео",
        slug="sto-geo-map",
        address="ул. Гео, 1",
        location=Point(44.68, 43.05, srid=4326),
        is_active=True,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    # точка ~ у станции (Владикавказ-подобные координаты)
    r = client.get(
        reverse("stations:nearby_map"),
        {"lat": "43.05", "lng": "44.68", "radius_km": "25"},
    )
    assert r.status_code == 200
    assert st.name in r.content.decode()
