"""Фаза 7: отзывы (PLAN-MVP-ATOMIC §7.1)."""

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
        phone="+79996660101",
        password="x",
        email="own7@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79996660102", password="x", email="cl7@t.test")


def _station(owner, slug="st-phase7"):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО Ф7",
        slug=slug,
        address="ул. 7",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )


def _completed_booking(owner, client_user, slug="st-phase7", hour=10):
    st = _station(owner, slug=slug)
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 4, 1),
        start_time=time(hour, 0),
        end_time=time(hour, 30),
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
    return st, b


@pytest.mark.django_db
def test_review_create_pending_returns_404(owner, client_user):
    st = _station(owner, slug="st-pend")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 4, 2),
        start_time=time(9, 0),
        end_time=time(9, 30),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.PENDING,
    )
    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    assert c.get(url).status_code == 404
    r_post = c.post(url, {"rating": 5, "text": "x"})
    assert r_post.status_code == 404


@pytest.mark.django_db
def test_second_review_integrity_error_shows_message(owner, client_user):
    _, b = _completed_booking(owner, client_user, slug="st-dup", hour=11)
    Review.objects.create(booking=b, rating=5, text="first")

    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    r = c.post(url, {"rating": 4, "text": "second"})
    assert r.status_code == 200
    msgs = [m.message for m in get_messages(r.wsgi_request)]
    assert any("уже добавлен" in m.lower() for m in msgs)


@pytest.mark.django_db
def test_avg_rating_on_station_detail_updates_after_reviews(owner, client_user):
    st = _station(owner, slug="st-avg")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2026, 4, 3)

    def slot(h):
        return TimeSlot.objects.create(
            bay=bay,
            date=d,
            start_time=time(h, 0),
            end_time=time(h, 30),
        )

    b1 = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot(10),
        car_info="A",
        contact_phone="+7",
        description="a",
        status=BookingStatus.COMPLETED,
    )
    b2 = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot(11),
        car_info="B",
        contact_phone="+7",
        description="b",
        status=BookingStatus.COMPLETED,
    )

    c = Client()
    c.force_login(client_user)
    c.post(
        reverse("cabinet:review_create", kwargs={"booking_pk": b1.pk}),
        {"rating": 4, "text": "ok"},
        follow=True,
    )
    r1 = c.get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r1.status_code == 200
    assert float(r1.context["station"].avg_rating) == 4.0

    c.post(
        reverse("cabinet:review_create", kwargs={"booking_pk": b2.pk}),
        {"rating": 2, "text": "meh"},
        follow=True,
    )
    r2 = c.get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r2.status_code == 200
    assert float(r2.context["station"].avg_rating) == 3.0


@pytest.mark.django_db
def test_review_text_escaped_on_station_detail(owner, client_user):
    st, b = _completed_booking(owner, client_user, slug="st-xss", hour=14)
    payload = "<script>alert(1)</script>\nline2"
    Review.objects.create(booking=b, rating=5, text=payload)

    r = Client().get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r.status_code == 200
    body = r.content.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


@pytest.mark.django_db
def test_review_already_exists_get_redirects_to_cabinet(owner, client_user):
    _, b = _completed_booking(owner, client_user, slug="st-redir", hour=15)
    Review.objects.create(booking=b, rating=3, text="y")

    c = Client()
    c.force_login(client_user)
    url = reverse("cabinet:review_create", kwargs={"booking_pk": b.pk})
    r = c.get(url, follow=False)
    assert r.status_code == 302
    assert r.url == reverse("cabinet:bookings")
