"""Подписка и месячная статистика на дашборде СТО (сценарий шаг 6)."""

from datetime import date, datetime, time

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import WorkBay
from apps.stations.sto_stats import monthly_booking_series_for_owner, subscription_rows_for_owner
from apps.stations.tests.test_phase5_owner import _grant_sto_offer_consent, _setup_station
from apps.users.models import User


@pytest.fixture
def owner_sub(db):
    u = User.objects.create_user(
        phone="+79991110001",
        password="x",
        email="sub@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    _grant_sto_offer_consent(u)
    return u


@pytest.mark.django_db
def test_subscription_rows_free_plan_visible(owner_sub):
    st = _setup_station(owner_sub, slug="sub-free")
    st.subscription_plan = SUBSCRIPTION_PLAN_FREE
    st.subscription_paid_until = None
    st.save()
    rows = subscription_rows_for_owner(owner_sub)
    assert len(rows) == 1
    assert rows[0]["plan_title"] == "Бесплатный"
    assert rows[0]["catalog_visible"] is True
    assert rows[0]["needs_attention"] is False


@pytest.mark.django_db
@override_settings(CATALOG_BYPASS_SUBSCRIPTION=True)
def test_subscription_rows_bypass_basic_expired_still_visible(owner_sub):
    st = _setup_station(owner_sub, slug="sub-bypass")
    st.subscription_plan = SUBSCRIPTION_PLAN_BASIC
    st.subscription_paid_until = date(2020, 1, 1)
    st.save()
    rows = subscription_rows_for_owner(owner_sub)
    assert rows[0]["catalog_visible"] is True
    assert rows[0]["needs_attention"] is False
    assert "без требования" in rows[0]["status_note"]


@pytest.mark.django_db
def test_subscription_rows_basic_expired_needs_attention(owner_sub):
    st = _setup_station(owner_sub, slug="sub-exp")
    st.subscription_plan = SUBSCRIPTION_PLAN_BASIC
    st.subscription_paid_until = date(2020, 1, 1)
    st.save()
    rows = subscription_rows_for_owner(owner_sub)
    assert rows[0]["needs_attention"] is True
    assert rows[0]["catalog_visible"] is False


@pytest.mark.django_db
def test_monthly_series_counts_non_canceled_only(owner_sub, db):
    client_u = User.objects.create_user(phone="+79991110002", password="x", email="cl@t.test")
    st = _setup_station(owner_sub, slug="stat-m")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot1 = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(8, 0),
        end_time=time(9, 0),
    )
    slot2 = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    b_ok = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot1,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.CONFIRMED,
    )
    b_can = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot2,
        car_info="B",
        contact_phone="+7",
        description="d",
        status=BookingStatus.CANCELED,
    )
    today = timezone.localdate()
    t_ok = timezone.make_aware(datetime.combine(today.replace(day=10), time(12, 0)))
    t_can = timezone.make_aware(datetime.combine(today.replace(day=11), time(12, 0)))
    Booking.objects.filter(pk=b_ok.pk).update(created_at=t_ok)
    Booking.objects.filter(pk=b_can.pk).update(created_at=t_can)

    series = monthly_booking_series_for_owner(owner_sub)
    today = timezone.localdate()
    cur = next(x for x in series if x["year"] == today.year and x["month"] == today.month)
    assert cur["count"] == 1


@pytest.mark.django_db
def test_dashboard_renders_subscription_and_chart_sections(owner_sub):
    _setup_station(owner_sub, slug="dash-ui")
    c = Client()
    c.force_login(owner_sub)
    r = c.get(reverse("sto_owner:dashboard"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Подписка и показ в каталоге" in body
    assert "Записи по месяцам" in body
