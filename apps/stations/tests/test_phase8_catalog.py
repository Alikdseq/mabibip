"""Фаза 8: монетизация и публичный каталог (PLAN-MVP-ATOMIC §8.1)."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79997770101",
        password="x",
        email="own8@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


def _station(owner, **kwargs):
    defaults = {
        "owner": owner,
        "name": "СТО Ф8",
        "slug": "st-f8",
        "address": "ул. 8",
        "subscription_plan": SUBSCRIPTION_PLAN_FREE,
        "subscription_paid_until": None,
        "is_active": True,
    }
    defaults.update(kwargs)
    return ServiceStation.objects.create(**defaults)


@pytest.mark.django_db
def test_basic_paid_until_yesterday_hidden_from_catalog_list(owner):
    """Регрессия 8.1.2: просрочка basic по дате скрывает СТО из списка."""
    today = timezone.localdate()
    st = _station(
        owner,
        slug="expired-basic",
        name="Просрочка",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=today - timedelta(days=1),
        is_active=True,
    )
    visible = _station(
        owner,
        slug="still-free",
        name="Free OK",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )

    client = Client()
    r = client.get(reverse("stations:list"))
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert st.slug not in slugs
    assert visible.slug in slugs


@pytest.mark.django_db
def test_booking_success_respects_catalog_visibility(owner):
    """Публичная страница успеха записи не обходит visible_in_catalog (шаг 8.1.1)."""
    today = timezone.localdate()
    hidden = _station(
        owner,
        slug="succ-no-cat",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=today - timedelta(days=1),
    )
    r = Client().get(
        reverse("stations:booking_success", kwargs={"slug": hidden.slug}),
    )
    assert r.status_code == 404
