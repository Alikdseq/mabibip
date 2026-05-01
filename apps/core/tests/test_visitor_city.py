"""Город посетителя: сессия и смена города."""

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.visitor_city import SESSION_KEY, list_allowed_city_labels
from apps.stations.models import District


@pytest.mark.django_db
def test_set_visitor_city_post_updates_session():
    District.objects.create(name="Центр", slug="c1", city_label="Владикавказ")
    District.objects.create(name="Юг", slug="c2", city_label="Москва")
    c = Client()
    c.get(reverse("home"))
    assert c.session.get(SESSION_KEY) in ("Владикавказ", "Москва")
    url = reverse("set_visitor_city")
    r = c.post(url, {"city_label": "Москва", "next": reverse("home")})
    assert r.status_code == 302
    assert c.session.get(SESSION_KEY) == "Москва"


@pytest.mark.django_db
def test_set_visitor_city_rejects_unknown():
    District.objects.create(name="Центр", slug="c1", city_label="Владикавказ")
    c = Client()
    c.get(reverse("home"))
    url = reverse("set_visitor_city")
    r = c.post(url, {"city_label": "НетТакого"})
    assert r.status_code == 302
    assert c.session.get(SESSION_KEY) == "Владикавказ"


@pytest.mark.django_db
@override_settings(APP_FOCUS_CITY_LABEL="Владикавказ")
def test_focus_city_limits_allowed_labels():
    District.objects.create(name="Центр", slug="fc1", city_label="Владикавказ")
    District.objects.create(name="Юг", slug="fc2", city_label="Москва")
    labels = list_allowed_city_labels()
    assert labels
    assert labels[0] == "Владикавказ"
    assert "Москва" in labels
