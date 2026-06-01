"""Отзывы с карточки станции без записи."""

from datetime import date, time

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import Review
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79997770101",
        password="x",
        email="own-open@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79997770102", password="x", email="cl-open@t.test")


def _station(owner, slug="st-open"):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО Open",
        slug=slug,
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


def _review_from_booking(booking, **kwargs):
    defaults = {
        "booking": booking,
        "author": booking.client,
        "station": booking.station,
        "rating": 5,
        "text": "ok",
    }
    defaults.update(kwargs)
    return Review.objects.create(**defaults)


@pytest.mark.django_db
def test_station_review_without_booking(owner, client_user):
    st = _station(owner)
    c = Client()
    c.force_login(client_user)
    url = reverse("stations:station_review_create", kwargs={"slug": st.slug})
    r = c.post(url, {"rating": 4, "text": "нормально"}, follow=True)
    assert r.status_code == 200
    rev = Review.objects.get(author=client_user, station=st)
    assert rev.booking_id is None
    assert rev.rating == 4


@pytest.mark.django_db
def test_station_review_duplicate_blocked(owner, client_user):
    st = _station(owner, slug="st-dup-open")
    Review.objects.create(author=client_user, station=st, rating=3, text="first")
    c = Client()
    c.force_login(client_user)
    url = reverse("stations:station_review_create", kwargs={"slug": st.slug})
    r = c.get(url, follow=False)
    assert r.status_code == 302
    msgs = [m.message for m in get_messages(r.wsgi_request)]
    assert any("уже оставили" in m.lower() for m in msgs)


@pytest.mark.django_db
def test_station_review_owner_forbidden(owner, client_user):
    st = _station(owner, slug="st-own")
    c = Client()
    c.force_login(owner)
    url = reverse("stations:station_review_create", kwargs={"slug": st.slug})
    r = c.post(url, {"rating": 5, "text": "x"}, follow=True)
    assert r.status_code == 200
    assert not Review.objects.filter(station=st).exists()


@pytest.mark.django_db
def test_cabinet_review_blocked_if_station_review_exists(owner, client_user):
    st = _station(owner, slug="st-cab-block")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 5, 1),
        start_time=time(10, 0),
        end_time=time(10, 30),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.COMPLETED,
    )
    Review.objects.create(author=client_user, station=st, rating=5, text="from card")
    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    r = c.get(url, follow=False)
    assert r.status_code == 302
    assert r.url == reverse("cabinet:bookings")


@pytest.mark.django_db
def test_detail_shows_leave_review_button(owner, client_user):
    st = _station(owner, slug="st-btn")
    c = Client()
    c.force_login(client_user)
    r = c.get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r.status_code == 200
    assert r.context["can_leave_station_review"] is True
    assert "Оставить отзыв" in r.content.decode()
