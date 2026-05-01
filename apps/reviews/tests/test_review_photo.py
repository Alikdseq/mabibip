"""Одно опциональное фото к отзыву (сценарий ЛК, публичная карточка СТО)."""

from datetime import date, time
from io import BytesIO
from tempfile import gettempdir
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import Review
from apps.reviews.tests.test_phase7 import _completed_booking, _station
from apps.stations.models import WorkBay
from apps.users.models import User


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (120, 90), color=(40, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.django_db
@override_settings(MEDIA_ROOT=gettempdir())
def test_review_create_with_photo_and_shown_on_station_detail(owner, client_user):
    _, b = _completed_booking(owner, client_user, slug="st-photo-1", hour=12)
    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    up = SimpleUploadedFile("v.png", _png_bytes(), content_type="image/png")
    r = c.post(
        url,
        {"rating": 5, "text": "Всё супер, фото чека", "photo": up},
    )
    assert r.status_code == 302
    rev = Review.objects.get(booking=b)
    assert rev.photo.name
    st = b.station
    d = c.get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert d.status_code == 200
    body = d.content.decode()
    assert "review-photo-wrap" in body


@pytest.mark.django_db
@patch("apps.reviews.forms.REVIEW_PHOTO_MAX_BYTES", 200)
def test_review_photo_rejects_file_larger_than_limit(owner, client_user):
    _, b = _completed_booking(owner, client_user, slug="st-photo-2", hour=13)
    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    big = SimpleUploadedFile("h.png", _png_bytes() * 5, content_type="image/png")
    r = c.post(
        url,
        {"rating": 5, "text": "текст", "photo": big},
    )
    assert r.status_code == 200
    assert not Review.objects.filter(booking=b).exists()
    err = r.content.decode()
    assert "больш" in err.lower() or "МБ" in err


@pytest.mark.django_db
@override_settings(MEDIA_ROOT=gettempdir())
def test_edit_review_clear_photo_removes_file():
    owner = User.objects.create_user(
        phone="+79992000001",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    cl = User.objects.create_user(phone="+79992000002", password="x", email="e@t.t")
    st = _station(owner, slug="st-ph-ed")
    bay = WorkBay.objects.create(station=st, name="P")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 5, 1),
        start_time=time(10, 0),
        end_time=time(10, 30),
    )
    b = Booking.objects.create(
        client=cl,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.COMPLETED,
    )
    rev = Review.objects.create(booking=b, rating=4, text="x")
    rev.photo.save(
        "o.png",
        SimpleUploadedFile("o.png", _png_bytes(), content_type="image/png"),
        save=True,
    )
    c = Client()
    c.force_login(cl)
    url = reverse("cabinet:review_edit", kwargs={"pk": rev.pk})
    r = c.post(
        url,
        {
            "rating": 4,
            "text": "x2",
            "photo-clear": "on",
        },
    )
    assert r.status_code == 302
    rev.refresh_from_db()
    assert not rev.photo
