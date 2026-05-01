"""Фаза F3: генерация слотов, Redis hold, идемпотентность (PLAN-FULL-TZ-ATOMIC)."""

from datetime import date, time

import pytest
from django.contrib.auth import get_user_model

from apps.bookings.models import TimeSlot, WorkingHours
from apps.bookings.redis_holds import acquire_or_refresh_slot_hold, delete_slot_hold
from apps.bookings.slot_generation import run_generate_weekly_slots
from apps.bookings.slot_rules import slot_is_bookable
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79993330101",
        password="x",
        email="f3o@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def station(owner):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО-F3",
        slug="sto-f3",
        address="ул. F3",
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
def test_f3_t1_generate_idempotent(bay):
    """F3.T1: повторный запуск генерации не плодит дубликаты."""
    ref = date(2031, 6, 9)
    WorkingHours.objects.create(
        bay=bay,
        weekday=ref.weekday(),
        opens_at=time(9, 0),
        closes_at=time(11, 0),
        slot_duration_minutes=60,
        breaks=[],
    )
    n1 = run_generate_weekly_slots(today=ref, days_ahead=0)
    assert n1 == 2
    count = TimeSlot.objects.filter(bay=bay, date=ref).count()
    n2 = run_generate_weekly_slots(today=ref, days_ahead=0)
    assert n2 == 0
    assert TimeSlot.objects.filter(bay=bay, date=ref).count() == count


@pytest.mark.django_db
def test_f3_t2_hold_blocks_other_user(bay):
    """F3.T2: hold блокирует чужую запись; снятие ключа — снова доступно."""
    u_a = User.objects.create_user(phone="+79993330201", password="x", email="a@t.test")
    u_b = User.objects.create_user(phone="+79993330202", password="x", email="b@t.test")
    today = date(2032, 2, 1)
    slot = _slot(bay, today)

    assert acquire_or_refresh_slot_hold(slot.pk, u_a.pk) is True
    assert slot_is_bookable(slot, for_user=u_b) is False
    assert slot_is_bookable(slot, for_user=u_a) is True

    delete_slot_hold(slot.pk)
    assert slot_is_bookable(slot, for_user=u_b) is True


@pytest.mark.django_db
def test_f3_t3_hold_race_second_user_loses(bay):
    """F3.T3: два клиента — один hold побеждает."""
    u_a = User.objects.create_user(phone="+79993330301", password="x", email="ra@t.test")
    u_b = User.objects.create_user(phone="+79993330302", password="x", email="rb@t.test")
    slot = _slot(bay, date(2032, 3, 1))

    assert acquire_or_refresh_slot_hold(slot.pk, u_a.pk) is True
    assert acquire_or_refresh_slot_hold(slot.pk, u_b.pk) is False
    assert acquire_or_refresh_slot_hold(slot.pk, u_a.pk) is True
