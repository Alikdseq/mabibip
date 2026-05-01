"""Календарь слотов СТО и ручное закрытие окон."""

from datetime import date, time

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.slot_rules import slot_is_bookable
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.stations.tests.test_phase5_owner import _grant_sto_offer_consent
from apps.users.models import User


@pytest.fixture
def owner_cal(db):
    u = User.objects.create_user(
        phone="+79998880101",
        password="x",
        email="cal@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    _grant_sto_offer_consent(u)
    return u


@pytest.fixture
def station_cal(owner_cal):
    return ServiceStation.objects.create(
        owner=owner_cal,
        name="Кал Тест",
        slug="cal-test",
        address="ул. Кал",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


@pytest.fixture
def client_cal(db):
    return User.objects.create_user(phone="+79998880102", password="x", email="clcal@t.test")


@pytest.mark.django_db
def test_slot_calendar_renders(owner_cal, station_cal):
    bay = WorkBay.objects.create(station=station_cal, name="Бокс 1")
    TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(10, 0),
        end_time=time(11, 0),
        is_available=True,
    )
    c = Client()
    c.force_login(owner_cal)
    r = c.get(reverse("sto_owner:slot_calendar"), {"station": station_cal.slug})
    assert r.status_code == 200
    assert "Календарь слотов".encode() in r.content


@pytest.mark.django_db
def test_toggle_block_closes_slot(owner_cal, station_cal):
    bay = WorkBay.objects.create(station=station_cal, name="Бокс 2")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(12, 0),
        end_time=time(13, 0),
        is_available=True,
    )
    c = Client()
    c.force_login(owner_cal)
    monday = timezone.localdate()
    url_toggle = reverse("sto_owner:slot_toggle_block", kwargs={"pk": slot.pk})
    r = c.post(
        url_toggle,
        {
            "action": "block",
            "note": "Обед",
            "week": monday.isoformat(),
            "station": station_cal.slug,
        },
    )
    assert r.status_code == 302
    slot.refresh_from_db()
    assert slot.is_available is False
    assert slot.manual_block_note == "Обед"
    assert slot_is_bookable(slot, now=timezone.now()) is False


@pytest.mark.django_db
def test_cannot_block_when_active_booking(owner_cal, station_cal, client_cal):
    bay = WorkBay.objects.create(station=station_cal, name="Бокс 3")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2035, 7, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        is_available=True,
    )
    Booking.objects.create(
        client=client_cal,
        station=station_cal,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="x",
        status=BookingStatus.CONFIRMED,
    )
    c = Client()
    c.force_login(owner_cal)
    r = c.post(
        reverse("sto_owner:slot_toggle_block", kwargs={"pk": slot.pk}),
        {"action": "block", "week": "2035-07-07", "station": station_cal.slug},
    )
    assert r.status_code == 302
    slot.refresh_from_db()
    assert slot.is_available is True


@pytest.mark.django_db
def test_foreign_owner_cannot_toggle(owner_cal, db):
    other = User.objects.create_user(
        phone="+79998880103",
        password="x",
        email="oth@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    _grant_sto_offer_consent(other)
    st = ServiceStation.objects.create(
        owner=other,
        name="Чужая",
        slug="other-cal",
        address="x",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(8, 0),
        end_time=time(9, 0),
    )
    c = Client()
    c.force_login(owner_cal)
    r = c.post(reverse("sto_owner:slot_toggle_block", kwargs={"pk": slot.pk}), {"action": "block"})
    assert r.status_code == 404
