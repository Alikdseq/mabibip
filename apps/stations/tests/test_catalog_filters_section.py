"""Фильтр section в каталоге и «Ещё» разделов услуг."""

from datetime import date, time

import pytest
from django.test import Client
from django.urls import reverse

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.constants import EXECUTOR_KIND_PRIVATE, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import CarBrand, ServiceCategory, ServiceSection, ServiceStation, WorkBay
from apps.users.models import User


@pytest.mark.django_db
def test_catalog_section_filter(owner):
    section = ServiceSection.objects.create(name="Тест раздел", slug="test-sec-filter", sort_order=1)
    cat = ServiceCategory.objects.create(name="Услуга в разделе", slug="svc-in-sec", section=section)
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО секция",
        slug="st-sec-f",
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        executor_kind=EXECUTOR_KIND_PRIVATE,
    )
    st.categories.add(cat)
    other = ServiceStation.objects.create(
        owner=owner,
        name="СТО другое",
        slug="st-other",
        address="ул. 2",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        executor_kind=EXECUTOR_KIND_PRIVATE,
    )
    r = Client().get(reverse("stations:list"), {"section": "test-sec-filter"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert "st-sec-f" in slugs
    assert "st-other" not in slugs


@pytest.mark.django_db
def test_catalog_brand_filter(owner):
    brand, _ = CarBrand.objects.get_or_create(
        slug="bmw",
        defaults={"name": "BMW", "sprite_key": "bmw", "sort_order": 10, "is_popular": True},
    )
    cat, _ = ServiceCategory.objects.get_or_create(
        slug="diag-bmw-filter",
        defaults={"name": "Диагностика BMW filter"},
    )
    st = ServiceStation.objects.create(
        owner=owner,
        name="BMW сервис",
        slug="bmw-st",
        address="ул. 3",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        executor_kind=EXECUTOR_KIND_PRIVATE,
    )
    st.categories.add(cat)
    st.car_brands.add(brand)
    other = ServiceStation.objects.create(
        owner=owner,
        name="Другой",
        slug="other-st",
        address="ул. 4",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
        executor_kind=EXECUTOR_KIND_PRIVATE,
    )
    r = Client().get(reverse("stations:list"), {"brand": "bmw"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert "bmw-st" in slugs
    assert "other-st" not in slugs


@pytest.mark.django_db
def test_homepage_includes_subaru_brand_from_db(owner):
    CarBrand.objects.get_or_create(
        slug="subaru",
        defaults={"name": "Subaru", "sprite_key": "subaru", "sort_order": 51, "is_popular": False},
    )
    r = Client().get(reverse("home"))
    assert r.status_code == 200
    assert "Subaru" in r.content.decode() or "subaru" in r.content.decode()
