"""Перенос времени: предложение СТО и ответ клиента."""

from datetime import date, datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.services import (
    client_accept_reschedule,
    client_decline_reschedule,
    owner_propose_booking_reschedule,
)
from apps.bookings.slot_rules import slot_is_bookable
from apps.legal.models import DocumentKey, UserConsent, get_current_version
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay

User = get_user_model()


def _grant_sto_offer_consent(user: User) -> None:
    ver = get_current_version(DocumentKey.STO_OFFER)
    if ver:
        UserConsent.objects.get_or_create(user=user, document_version=ver)


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        phone="+79994440101",
        password="x",
        email="rs-o@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    u.sto_moderation_status = User.StoModerationStatus.APPROVED
    u.save(update_fields=["sto_moderation_status"])
    _grant_sto_offer_consent(u)
    return u


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79994440102", password="x", email="rs-c@t.test")


@pytest.fixture
def station(owner):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО-RS",
        slug="sto-rs",
        address="ул. RS",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


@pytest.fixture
def bay(station):
    return WorkBay.objects.create(station=station, name="П1")


def _slot(bay, d, start="10:00", end="11:00", **kwargs):
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    return TimeSlot.objects.create(
        bay=bay,
        date=d,
        start_time=time(h1, m1),
        end_time=time(h2, m2),
        **kwargs,
    )


@pytest.mark.django_db
def test_proposed_slot_not_bookable_for_others(bay, station, client_user, owner):
    today = date(2031, 5, 10)
    now = timezone.make_aware(datetime(2031, 5, 10, 8, 0))
    s0 = _slot(bay, today, start="10:00", end="11:00")
    s1 = _slot(bay, today, start="14:00", end="15:00")
    b0 = Booking.objects.create(
        client=client_user,
        station=station,
        slot=s0,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )
    owner_propose_booking_reschedule(booking=b0, actor=owner, new_slot_id=s1.pk, owner_message="занято")
    assert slot_is_bookable(s1, now=now) is False
    assert slot_is_bookable(s1, now=now, exclude_reschedule_for_booking_id=b0.pk) is True


@pytest.mark.django_db
def test_client_accept_moves_slot_and_confirms(bay, station, client_user, owner):
    today = date(2031, 5, 11)
    s0 = _slot(bay, today, start="10:00", end="11:00")
    s1 = _slot(bay, today, start="15:00", end="16:00")
    b0 = Booking.objects.create(
        client=client_user,
        station=station,
        slot=s0,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )
    owner_propose_booking_reschedule(booking=b0, actor=owner, new_slot_id=s1.pk)
    b0.refresh_from_db()
    client_accept_reschedule(booking=b0, client=client_user)
    b0.refresh_from_db()
    assert b0.slot_id == s1.pk
    assert b0.status == BookingStatus.CONFIRMED
    assert b0.reschedule_proposed_slot_id is None


@pytest.mark.django_db
def test_client_decline_clears_proposal(bay, station, client_user, owner):
    today = date(2031, 5, 12)
    s0 = _slot(bay, today, start="10:00", end="11:00")
    s1 = _slot(bay, today, start="12:00", end="13:00")
    b0 = Booking.objects.create(
        client=client_user,
        station=station,
        slot=s0,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )
    owner_propose_booking_reschedule(booking=b0, actor=owner, new_slot_id=s1.pk)
    b0.refresh_from_db()
    client_decline_reschedule(booking=b0, client=client_user)
    b0.refresh_from_db()
    assert b0.slot_id == s0.pk
    assert b0.status == BookingStatus.PENDING
    assert b0.reschedule_proposed_slot_id is None


@pytest.mark.django_db
def test_reschedule_slots_endpoint(owner, client_user, bay, station):
    # Завтра: иначе «сегодняшние» утренние окна могут считаться прошедшими по времени суток.
    day = timezone.localdate() + timedelta(days=1)
    s0 = _slot(bay, day, start="10:00", end="11:00")
    s1 = _slot(bay, day, start="11:00", end="12:00")
    b0 = Booking.objects.create(
        client=client_user,
        station=station,
        slot=s0,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )
    c = Client()
    c.force_login(owner)
    url = reverse("sto_owner:booking_reschedule_slots", kwargs={"pk": b0.pk})
    r = c.get(url, {"date": day.isoformat()})
    assert r.status_code == 200
    data = r.json()
    ids = {x["id"] for x in data["slots"]}
    assert s1.pk in ids
    assert s0.pk not in ids
