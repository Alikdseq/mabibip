"""Фаза 3: СТО, каталог, видимость, отзывы (PLAN-MVP-ATOMIC)."""

from datetime import date, datetime, time
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone as dj_tz
from django.urls import reverse
from PIL import Image

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import Review
from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, StationPhoto, WorkBay
from apps.stations.selectors import annotate_station_ratings, station_has_slots_today
from apps.stations.visibility import station_accepts_online_booking, station_is_visible
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79994440101",
        password="x",
        email="owner@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


def _station(owner, **kwargs):
    defaults = {
        "owner": owner,
        "name": "Тест СТО",
        "slug": "test-sto",
        "address": "ул. Тестовая, 1",
        "description": "Описание",
        "subscription_plan": SUBSCRIPTION_PLAN_FREE,
        "subscription_paid_until": None,
        "is_active": True,
    }
    defaults.update(kwargs)
    return ServiceStation.objects.create(**defaults)


def _tiny_image(name="t.png"):
    buf = BytesIO()
    Image.new("RGB", (8, 8), color=(120, 40, 200)).save(buf, format="PNG")
    buf.seek(0)
    from django.core.files.base import ContentFile

    return ContentFile(buf.read(), name=name)


@pytest.mark.django_db
def test_is_visible_in_catalog_matrix(owner):
    ref = date(2026, 6, 15)
    s_inactive = _station(
        owner,
        slug="a",
        is_active=False,
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    assert s_inactive.is_visible_in_catalog(ref) is False

    s_free = _station(owner, slug="b", subscription_plan=SUBSCRIPTION_PLAN_FREE)
    assert station_is_visible(s_free, ref) is True

    s_basic_ok = _station(
        owner,
        slug="c",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=ref,
    )
    assert s_basic_ok.is_visible_in_catalog(ref) is True

    s_basic_old = _station(
        owner,
        slug="d",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=ref.replace(day=1),
    )
    assert s_basic_old.is_visible_in_catalog(ref) is False

    s_basic_null = _station(
        owner,
        slug="e",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=None,
    )
    assert s_basic_null.is_visible_in_catalog(ref) is False


@pytest.mark.django_db
def test_online_booking_when_basic_unpaid_catalog_hidden_but_station_active(owner):
    """Без оплаты Basic станция может не быть в каталоге, но слоты на её странице должны быть доступны."""
    ref = date(2026, 9, 10)
    st = _station(
        owner,
        slug="booking-basic-gap",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=None,
    )
    assert station_is_visible(st, ref) is False
    assert station_accepts_online_booking(st, ref) is True


@pytest.mark.django_db
def test_online_booking_false_when_inactive(owner):
    ref = date(2026, 9, 11)
    st = _station(owner, slug="inactive-bk", is_active=False)
    assert station_accepts_online_booking(st, ref) is False


@pytest.mark.django_db
def test_station_photo_max_five(owner):
    st = _station(owner, slug="ph")
    for i in range(5):
        StationPhoto.objects.create(station=st, image=_tiny_image(f"{i}.png"), order=i)
    sixth = StationPhoto(station=st, image=_tiny_image("5.png"), order=5)
    with pytest.raises(ValidationError):
        sixth.full_clean()


@pytest.mark.django_db
def test_visible_in_catalog_queryset(owner):
    ref = date(2026, 4, 1)
    _station(owner, slug="v1", subscription_plan=SUBSCRIPTION_PLAN_FREE)
    _station(
        owner,
        slug="v2",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=ref,
    )
    _station(
        owner,
        slug="v3",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=ref.replace(year=2020),
    )
    ids = set(ServiceStation.objects.visible_in_catalog(today=ref).values_list("slug", flat=True))
    assert "v1" in ids and "v2" in ids and "v3" not in ids


@pytest.mark.django_db
def test_hidden_subscription_station_detail_visible_booking_off(owner):
    ref = date(2026, 8, 1)
    hidden = _station(
        owner,
        slug="hidden-sto",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=ref.replace(year=2020),
        is_active=True,
    )
    client = Client()
    url = reverse("stations:detail", kwargs={"slug": hidden.slug})
    r = client.get(url)
    assert r.status_code == 200
    assert r.context["can_book_online"] is False
    body = r.content.decode()
    assert "не принимает онлайн-записи" in body
    slots_url = reverse("stations:slots_partial", kwargs={"slug": hidden.slug})
    rs = client.get(slots_url)
    assert rs.status_code == 200
    assert "не принимает онлайн-записи" in rs.content.decode()


@pytest.mark.django_db
def test_inactive_station_detail_404(owner):
    st = _station(owner, slug="inactive-sto", is_active=False)
    r = Client().get(reverse("stations:detail", kwargs={"slug": st.slug}))
    assert r.status_code == 404


@pytest.mark.django_db
def test_search_q_filters_list(owner):
    _station(
        owner,
        slug="find-alfa",
        name="Альфа Сервис",
        address="ул. Лесная",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    _station(
        owner,
        slug="find-beta",
        name="Бета",
        address="ул. Полевая, 7",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    client = Client()
    r = client.get(reverse("stations:list"), {"q": "Полевая"})
    assert r.status_code == 200
    slugs = [s.slug for s in r.context["stations"]]
    assert "find-beta" in slugs and "find-alfa" not in slugs


@pytest.mark.django_db
def test_avg_rating_two_reviews(owner):
    client_user = User.objects.create_user(phone="+79994440102", password="x", email="c@t.test")
    client_user2 = User.objects.create_user(phone="+79994440103", password="x", email="c2@t.test")
    st = _station(owner, slug="rate-sto", subscription_plan=SUBSCRIPTION_PLAN_FREE)
    bay = WorkBay.objects.create(station=st, name="П1")
    slot1 = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 1, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    slot2 = TimeSlot.objects.create(
        bay=bay,
        date=date(2026, 1, 2),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    b1 = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot1,
        car_info="A111AA",
        contact_phone="+7000",
        description="x",
        status=BookingStatus.COMPLETED,
    )
    b2 = Booking.objects.create(
        client=client_user2,
        station=st,
        slot=slot2,
        car_info="B222BB",
        contact_phone="+7000",
        description="y",
        status=BookingStatus.COMPLETED,
    )
    Review.objects.create(
        booking=b1, author=client_user, station=st, rating=4, text="норм"
    )
    Review.objects.create(
        booking=b2, author=client_user2, station=st, rating=2, text="так себе"
    )

    qs = annotate_station_ratings(ServiceStation.objects.filter(pk=st.pk))
    row = qs.get()
    assert float(row.avg_rating) == pytest.approx(3.0)


@pytest.mark.django_db
def test_station_has_slots_today_respects_booking(owner):
    today = date(2026, 7, 1)
    st = _station(owner, slug="slot-sto", subscription_plan=SUBSCRIPTION_PLAN_FREE)
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=today,
        start_time=time(9, 0),
        end_time=time(10, 0),
        is_available=True,
    )
    assert station_has_slots_today(st.pk, today) is True

    u = User.objects.create_user(phone="+79994440103", password="x", email="book@t.test")
    Booking.objects.create(
        client=u,
        station=st,
        slot=slot,
        car_info="x",
        contact_phone="1",
        description="d",
        status=BookingStatus.PENDING,
    )
    assert station_has_slots_today(st.pk, today) is False


@pytest.mark.django_db
def test_station_has_slots_today_excludes_past_windows_same_calendar_day(owner):
    """На «сегодня» учитываются только слоты, время начала которых ещё не наступило (локально)."""
    today = date(2031, 5, 20)
    noon = dj_tz.make_aware(datetime(2031, 5, 20, 14, 0, 0))
    st = _station(owner, slug="sto-today-cutoff", subscription_plan=SUBSCRIPTION_PLAN_FREE)
    bay = WorkBay.objects.create(station=st, name="П2")
    TimeSlot.objects.create(
        bay=bay,
        date=today,
        start_time=time(9, 0),
        end_time=time(10, 0),
        is_available=True,
    )
    with (
        patch("apps.stations.selectors.dj_tz.localdate", return_value=today),
        patch("apps.stations.selectors.dj_tz.now", return_value=noon),
        patch("apps.stations.selectors.dj_tz.localtime", return_value=noon),
    ):
        assert station_has_slots_today(st.pk, today) is False

    TimeSlot.objects.create(
        bay=bay,
        date=today,
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_available=True,
    )
    with (
        patch("apps.stations.selectors.dj_tz.localdate", return_value=today),
        patch("apps.stations.selectors.dj_tz.now", return_value=noon),
        patch("apps.stations.selectors.dj_tz.localtime", return_value=noon),
    ):
        assert station_has_slots_today(st.pk, today) is True
