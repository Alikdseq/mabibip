"""Фаза 4: слоты, бронирование, письма, автоотмена (PLAN-MVP-ATOMIC)."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.exceptions import BookingSlotConflictError, SlotNotBookableError
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.services import create_booking_request, expire_unconfirmed_bookings_now
from apps.bookings.tasks import send_booking_reminders_2h
from apps.bookings.slot_rules import slot_is_bookable
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79993330101",
        password="x",
        email="o4@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79993330102", password="x", email="c4@t.test")


@pytest.fixture
def station(owner):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО-4",
        slug="sto-four",
        address="ул. 4",
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
def test_slot_is_bookable_matrix(bay, client_user, station):
    today = date(2030, 1, 15)
    # 9:00 — свободное окно 10:00 ещё в будущем; 12:00+ — дневные слоты 10:00 уже в прошлом
    now = timezone.make_aware(datetime(2030, 1, 15, 9, 0))
    past_day = _slot(bay, date(2029, 1, 1))
    assert slot_is_bookable(past_day, now=now) is False

    free = _slot(bay, today)
    assert slot_is_bookable(free, now=now) is True
    now_afternoon = timezone.make_aware(datetime(2030, 1, 15, 12, 0))
    assert slot_is_bookable(free, now=now_afternoon) is False

    off = _slot(bay, today, start="12:00", end="13:00", is_available=False)
    assert slot_is_bookable(off, now=now) is False

    taken = _slot(bay, today, start="14:00", end="15:00")
    Booking.objects.create(
        client=client_user,
        station=station,
        slot=taken,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )
    assert slot_is_bookable(taken, now=now) is False

    canceled = _slot(bay, today, start="16:00", end="17:00")
    Booking.objects.create(
        client=client_user,
        station=station,
        slot=canceled,
        car_info="B",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.CANCELED,
    )
    assert slot_is_bookable(canceled, now=now) is True


@pytest.mark.django_db
def test_create_booking_second_fails(bay, station, client_user):
    today = date(2030, 2, 1)
    now = timezone.make_aware(datetime(2030, 2, 1, 10, 0))
    slot = _slot(bay, today)
    create_booking_request(
        client=client_user,
        slot_id=slot.pk,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        now=now,
        send_notification=False,
    )
    with pytest.raises(SlotNotBookableError):
        create_booking_request(
            client=client_user,
            slot_id=slot.pk,
            car_info="B",
            contact_phone="+79990001122",
            description="y",
            now=now,
            send_notification=False,
        )


@pytest.mark.django_db
def test_after_booking_slot_not_in_bookable_list(bay, station, client_user):
    today = date(2030, 3, 1)
    now = timezone.make_aware(datetime(2030, 3, 1, 8, 0))
    slot = _slot(bay, today)
    create_booking_request(
        client=client_user,
        slot_id=slot.pk,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        now=now,
        send_notification=False,
    )
    assert slot_is_bookable(slot, now=now) is False


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_expire_unconfirmed_bookings(mock_send, bay, station, client_user):
    # Слот на завтра, чтобы после отмены брони он оставался «в будущем» при любой текущей дате прогона теста.
    tomorrow = timezone.localdate() + timedelta(days=1)
    slot = _slot(bay, tomorrow)
    deadline = timezone.now() - timedelta(hours=2)
    b = Booking.objects.create(
        client=client_user,
        station=station,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=deadline,
    )
    later = timezone.now()
    assert slot_is_bookable(slot, now=later) is False
    from django.core.management import call_command

    with TestCase.captureOnCommitCallbacks(execute=True):
        call_command("expire_unconfirmed_bookings")
    b.refresh_from_db()
    assert b.status == BookingStatus.CANCELED
    assert slot_is_bookable(slot, now=later) is True
    mock_send.assert_called()
    assert client_user.email in mock_send.call_args.kwargs["recipient_list"]


@pytest.mark.django_db
def test_booking_form_requires_login(bay, station):
    today = date(2030, 5, 1)
    slot = _slot(bay, today)
    c = Client()
    url = reverse("stations:booking_form", kwargs={"slug": station.slug, "slot_id": slot.pk})
    r = c.get(url)
    assert r.status_code == 302

    r = c.get(url, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert r.headers.get("HX-Redirect")
    assert "login" in r.headers["HX-Redirect"]


@pytest.mark.django_db
def test_booking_form_wrong_station_404(owner, client_user):
    st_a = ServiceStation.objects.create(
        owner=owner,
        name="A",
        slug="st-a",
        address="a",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    st_b = ServiceStation.objects.create(
        owner=owner,
        name="B",
        slug="st-b",
        address="b",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
    )
    bay_a = WorkBay.objects.create(station=st_a, name="p")
    slot = _slot(bay_a, date(2030, 6, 1))
    c = Client()
    c.force_login(client_user)
    url = reverse("stations:booking_form", kwargs={"slug": st_b.slug, "slot_id": slot.pk})
    r = c.get(url)
    assert r.status_code == 404


@pytest.mark.django_db(transaction=True)
@patch("apps.bookings.mail.send_mail")
def test_mail_sto_new_booking_called(mock_send, bay, station, client_user, owner):
    today = date(2030, 7, 1)
    now = timezone.make_aware(datetime(2030, 7, 1, 9, 0))
    slot = _slot(bay, today)
    create_booking_request(
        client=client_user,
        slot_id=slot.pk,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        now=now,
        send_notification=True,
        request=None,
    )
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert owner.email in kwargs["recipient_list"]


@pytest.mark.django_db
@patch("apps.bookings.slot_generation.run_generate_slots_for_station")
def test_slots_partial_empty_day(mock_gen, bay, station):
    """Без автогенерации слотов на день может не быть окон — проверяем пустой partial."""
    mock_gen.return_value = 0
    c = Client()
    url = reverse("stations:slots_partial", kwargs={"slug": station.slug})
    r = c.get(url, {"date": "2030-08-10"})
    assert r.status_code == 200
    assert "нет свободных окон" in r.content.decode().lower()


@pytest.mark.django_db
def test_slots_partial_clamps_date_to_catalog_window(bay, station):
    """Дата вне7-дневного окна приводится к допустимой (без произвольного сканирования)."""
    c = Client()
    url = reverse("stations:slots_partial", kwargs={"slug": station.slug})
    far = (timezone.localdate() + timedelta(days=365)).isoformat()
    r = c.get(url, {"date": far})
    assert r.status_code == 200
    assert r.context["day"] <= timezone.localdate() + timedelta(days=6)


@pytest.mark.django_db
def test_unique_in_progress_per_slot_db_constraint(bay, station, client_user):
    """Две заявки in_progress на один слот нарушают частичный уникальный индекс."""
    today = date(2030, 9, 2)
    slot = _slot(bay, today)
    Booking.objects.create(
        client=client_user,
        station=station,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        status=BookingStatus.IN_PROGRESS,
    )
    u2 = User.objects.create_user(phone="+79993330104", password="x", email="u3@t.test")
    with pytest.raises(IntegrityError):
        Booking.objects.create(
            client=u2,
            station=station,
            slot=slot,
            car_info="B",
            contact_phone="+79990003344",
            description="y",
            status=BookingStatus.IN_PROGRESS,
        )


@pytest.mark.django_db
def test_unique_pending_per_slot_db_constraint(bay, station, client_user):
    """Две активные заявки pending на один слот нарушают частичный уникальный индекс."""
    today = date(2030, 9, 1)
    slot = _slot(bay, today)
    dl = timezone.now() + timedelta(hours=1)
    Booking.objects.create(
        client=client_user,
        station=station,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=dl,
    )
    u2 = User.objects.create_user(phone="+79993330103", password="x", email="u2@t.test")
    with pytest.raises(IntegrityError):
        Booking.objects.create(
            client=u2,
            station=station,
            slot=slot,
            car_info="B",
            contact_phone="+79990003344",
            description="y",
            status=BookingStatus.PENDING,
            sto_confirm_deadline=dl,
        )


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_expire_unconfirmed_bookings_now(mock_send, bay, station, client_user):
    today = date(2030, 11, 1)
    slot = _slot(bay, today)
    past = timezone.now() - timedelta(hours=2)
    b = Booking.objects.create(
        client=client_user,
        station=station,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=past,
    )
    with TestCase.captureOnCommitCallbacks(execute=True):
        n = expire_unconfirmed_bookings_now(now=timezone.now())
    assert n == 1
    b.refresh_from_db()
    assert b.status == BookingStatus.CANCELED
    mock_send.assert_called()


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_send_booking_reminders_2h(mock_send, bay, station, client_user):
    today = date(2031, 2, 1)
    now = timezone.make_aware(datetime(2031, 2, 1, 10, 0))
    slot = _slot(bay, today, start="12:00", end="13:00")
    Booking.objects.create(
        client=client_user,
        station=station,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="x",
        status=BookingStatus.CONFIRMED,
    )
    with patch("django.utils.timezone.now", return_value=now):
        n = send_booking_reminders_2h()
    assert n == 1
    mock_send.assert_called_once()
    b = Booking.objects.get(slot=slot)
    assert b.reminder_2h_sent_at == now


@pytest.mark.django_db
def test_create_booking_wraps_integrity_as_conflict(bay, station, client_user):
    """Сервис оборачивает гонку на уровне БД в BookingSlotConflictError."""
    today = date(2030, 10, 1)
    slot = _slot(bay, today)
    with patch.object(Booking, "save", side_effect=IntegrityError("conflict")):
        with pytest.raises(BookingSlotConflictError):
            create_booking_request(
                client=client_user,
                slot_id=slot.pk,
                car_info="A",
                contact_phone="+79990001122",
                description="x",
                now=timezone.now(),
                send_notification=False,
            )
