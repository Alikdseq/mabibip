"""Фаза 6: ЛК клиента (PLAN-MVP-ATOMIC)."""

from datetime import time, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import Review
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79995550101",
        password="x",
        email="own@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_a(db):
    return User.objects.create_user(phone="+79995550102", password="x", email="a@t.test")


@pytest.fixture
def client_b(db):
    return User.objects.create_user(phone="+79995550103", password="x", email="b@t.test")


def _station(owner, slug="st-cab"):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО Каб",
        slug=slug,
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


@pytest.mark.django_db
def test_cabinet_hub_requires_login():
    r = Client().get(reverse("cabinet:index"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_cabinet_hub_renders_authenticated(client_a):
    c = Client()
    c.force_login(client_a)
    r = c.get(reverse("cabinet:index"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Личный кабинет" in body
    assert reverse("cabinet:bookings") in body


@pytest.mark.django_db
def test_client_sees_only_own_bookings(owner, client_a, client_b):
    st = _station(owner)
    bay = WorkBay.objects.create(station=st, name="П1")
    d = timezone.localdate()

    def slot(h):
        return TimeSlot.objects.create(
            bay=bay,
            date=d,
            start_time=time(h, 0),
            end_time=time(h, 30),
        )

    ba = Booking.objects.create(
        client=client_a,
        station=st,
        slot=slot(9),
        car_info="AA",
        contact_phone="+7",
        description="x",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    bb = Booking.objects.create(
        client=client_b,
        station=st,
        slot=slot(10),
        car_info="BB",
        contact_phone="+7",
        description="y",
        status=BookingStatus.CONFIRMED,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )

    c = Client()
    c.force_login(client_a)
    r = c.get(reverse("cabinet:bookings"))
    assert r.status_code == 200
    ids = [b.pk for b in r.context["bookings"]]
    assert ba.pk in ids
    assert bb.pk not in ids


@pytest.mark.django_db
def test_review_link_only_completed_without_review(owner, client_a):
    st = _station(owner, slug="st-rev")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = timezone.localdate()

    def mk_booking(h, status):
        sl = TimeSlot.objects.create(
            bay=bay,
            date=d,
            start_time=time(h, 0),
            end_time=time(h, 30),
        )
        return Booking.objects.create(
            client=client_a,
            station=st,
            slot=sl,
            car_info="X",
            contact_phone="+7",
            description="d",
            status=status,
            sto_confirm_deadline=timezone.now() + timedelta(hours=1),
        )

    b_pending = mk_booking(11, BookingStatus.PENDING)
    b_done = mk_booking(12, BookingStatus.COMPLETED)
    b_done_reviewed = mk_booking(13, BookingStatus.COMPLETED)
    Review.objects.create(booking=b_done_reviewed, rating=5, text="ok")

    c = Client()
    c.force_login(client_a)
    r = c.get(reverse("cabinet:bookings"))
    body = r.content.decode()
    assert "Оставить отзыв" in body
    assert reverse("cabinet:review_create", kwargs={"booking_pk": b_done.pk}) in body
    assert reverse("cabinet:review_create", kwargs={"booking_pk": b_pending.pk}) not in body
    assert reverse("cabinet:review_create", kwargs={"booking_pk": b_done_reviewed.pk}) not in body
