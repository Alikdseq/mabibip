from __future__ import annotations

from datetime import date, time

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.core.visitor_city import SESSION_KEY as VISITOR_CITY_SESSION_KEY
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import District, ServiceCategory, ServiceStation, WorkBay
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79990001111",
        password="x",
        is_phone_verified=True,
        is_sto_owner=True,
    )


@pytest.mark.django_db
def test_f8_t1_search_finds_partial_or_category(owner):
    d, _ = District.objects.get_or_create(name="Центр", slug="f8-dist", defaults={"city_label": "Тестград"})
    cat, _ = ServiceCategory.objects.get_or_create(name="Шиномонтаж", slug="shinomontazh")
    a = ServiceStation.objects.create(
        owner=owner,
        name="Альфа Сервис",
        slug="f8-alfa",
        address="ул. Лесная",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    b = ServiceStation.objects.create(
        owner=owner,
        name="Бета",
        slug="f8-beta",
        address="ул. Полевая, 7",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    b.categories.add(cat)

    c = Client()
    s = c.session
    s[VISITOR_CITY_SESSION_KEY] = "Тестград"
    s.save()
    r1 = c.get(reverse("stations:list"), {"q": "льфа"})
    assert r1.status_code == 200
    slugs1 = [s.slug for s in r1.context["stations"]]
    assert "f8-alfa" in slugs1

    r2 = c.get(reverse("stations:list"), {"q": "шином"})
    assert r2.status_code == 200
    slugs2 = [s.slug for s in r2.context["stations"]]
    assert "f8-beta" in slugs2


@pytest.mark.django_db
def test_f8_t2_filter_slots_today_excludes_without_slots(owner):
    today = timezone.localdate()
    d, _ = District.objects.get_or_create(name="Центр", slug="f8-dist2", defaults={"city_label": "Тестград"})

    now_t = timezone.localtime(timezone.now()).time()
    start_h = (now_t.hour + 2) % 24
    # Поскольку selector для "today" учитывает только start_time > now.time(),
    # ставим слот гарантированно в будущем.
    start = time(start_h, 0)
    end = time((start_h + 1) % 24, 0)

    st_with = ServiceStation.objects.create(
        owner=owner,
        name="Есть слоты",
        slug="f8-with",
        address="ул. 1",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st_with, name="П1")
    TimeSlot.objects.create(
        bay=bay,
        date=today,
        start_time=start,
        end_time=end,
        is_available=True,
    )

    st_without = ServiceStation.objects.create(
        owner=owner,
        name="Нет слотов",
        slug="f8-without",
        address="ул. 2",
        district=d,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay2 = WorkBay.objects.create(station=st_without, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay2,
        date=today,
        start_time=start,
        end_time=end,
        is_available=True,
    )
    u = User.objects.create_user(phone="+79990002222", password="x", is_phone_verified=True)
    Booking.objects.create(
        client=u,
        station=st_without,
        slot=slot,
        car_info="x",
        contact_phone="1",
        description="d",
        status=BookingStatus.PENDING,
    )

    # стабилизируем "today" внутри view
    c = Client()
    s = c.session
    s[VISITOR_CITY_SESSION_KEY] = "Тестград"
    s.save()
    with timezone.override("Europe/Moscow"):
        r = c.get(reverse("stations:list"), {"slots_today": "1"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert "f8-with" in slugs
    assert "f8-without" not in slugs

