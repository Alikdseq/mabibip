"""Фаза B: ЛК клиента — отмена записи, избранное, авто, отзыв edit."""

from datetime import date, datetime, time, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.services import client_cancel_booking, client_cancel_booking_precheck
from apps.reviews.models import Review
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.users.models import FavoriteStation, SavedCar, User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79996660101",
        password="x",
        email="own6b@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_u(db):
    return User.objects.create_user(phone="+79996660102", password="x", email="cl6b@t.test")


def _st(owner):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО 6B",
        slug="sto-6b",
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


@pytest.mark.django_db
def test_client_cancel_precheck_ok_and_too_late(owner, client_u):
    st = _st(owner)
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2030, 2, 1)
    slot = TimeSlot.objects.create(
        bay=bay,
        date=d,
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    b = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="x",
        status=BookingStatus.CONFIRMED,
    )
    ok_time = timezone.make_aware(datetime(2030, 2, 1, 7, 0))
    assert client_cancel_booking_precheck(b, client_u, now=ok_time) is None

    late_time = timezone.make_aware(datetime(2030, 2, 1, 8, 30))
    assert client_cancel_booking_precheck(b, client_u, now=late_time) is not None

    client_cancel_booking(booking=b, client=client_u, now=ok_time)
    b.refresh_from_db()
    assert b.status == BookingStatus.CANCELED


@pytest.mark.django_db
def test_favorite_toggle_add_remove(client_u, owner):
    st = _st(owner)
    c = Client()
    c.force_login(client_u)
    url = reverse("cabinet:favorite_toggle", kwargs={"slug": st.slug})
    assert not FavoriteStation.objects.filter(user=client_u, station=st).exists()
    r = c.post(url)
    assert r.status_code == 302
    assert FavoriteStation.objects.filter(user=client_u, station=st).exists()
    r2 = c.post(url)
    assert r2.status_code == 302
    assert not FavoriteStation.objects.filter(user=client_u, station=st).exists()


@pytest.mark.django_db
def test_saved_car_create(client_u):
    c = Client()
    c.force_login(client_u)
    url = reverse("cabinet:car_add")
    r = c.post(
        url,
        {"license_plate": "а777аа777", "brand_model": "Vesta", "vin": ""},
    )
    assert r.status_code == 302
    car = SavedCar.objects.get(user=client_u)
    assert car.license_plate == "А777АА777"


@pytest.mark.django_db
def test_review_edit_within_window(client_u, owner):
    st = _st(owner)
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2030, 3, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    b = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="x",
        status=BookingStatus.COMPLETED,
    )
    rev = Review.objects.create(booking=b, rating=4, text="ok")
    c = Client()
    c.force_login(client_u)
    edit_url = reverse("cabinet:review_edit", kwargs={"pk": rev.pk})
    r = c.get(edit_url)
    assert r.status_code == 200
    r2 = c.post(edit_url, {"rating": 5, "text": "отлично"})
    assert r2.status_code == 302
    rev.refresh_from_db()
    assert rev.rating == 5
    assert "отлично" in rev.text


@pytest.mark.django_db
def test_booking_cancel_view(client_u, owner):
    st = _st(owner)
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2030, 4, 1)
    slot = TimeSlot.objects.create(
        bay=bay,
        date=d,
        start_time=time(15, 0),
        end_time=time(16, 0),
    )
    b = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="x",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    c = Client()
    c.force_login(client_u)
    from unittest.mock import patch

    frozen = timezone.make_aware(datetime(2030, 4, 1, 12, 0))
    with patch("apps.bookings.services.timezone.now", return_value=frozen):
        r = c.post(reverse("cabinet:booking_cancel", kwargs={"pk": b.pk}))
    assert r.status_code == 302
    b.refresh_from_db()
    assert b.status == BookingStatus.CANCELED
