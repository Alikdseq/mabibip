"""Фаза 5: ЛК владельца СТО (PLAN-MVP-ATOMIC)."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import Review
from apps.bookings.services import apply_owner_booking_transition
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import CarBrand, ServiceCategory, ServiceStation, StationServiceOffer, WorkBay
from apps.stations.owner_forms import StationServiceOfferFormSet
from apps.legal.models import DocumentKey, UserConsent, get_current_version
from apps.stations.owner_views import _bookings_all_upcoming_qs, _month_stats_booking_count
from apps.users.models import User


def _grant_sto_offer_consent(user: User) -> None:
    """После F0 владелец СТО должен принять оферту — иначе middleware редиректит с /sto/cabinet/."""
    ver = get_current_version(DocumentKey.STO_OFFER)
    if ver:
        UserConsent.objects.get_or_create(user=user, document_version=ver)


@pytest.fixture
def owner1(db):
    u = User.objects.create_user(
        phone="+79992220101",
        password="x",
        email="own1@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    _grant_sto_offer_consent(u)
    return u


@pytest.fixture
def owner2(db):
    u = User.objects.create_user(
        phone="+79992220102",
        password="x",
        email="own2@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    _grant_sto_offer_consent(u)
    return u


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79992220001", password="x", email="cl@t.test")


def _setup_station(owner, slug="sto-o", plan=SUBSCRIPTION_PLAN_FREE, paid_until=None):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО",
        slug=slug,
        address="ул. 1",
        subscription_plan=plan,
        subscription_paid_until=paid_until,
        is_active=True,
    )


@pytest.mark.django_db
def test_foreign_owner_post_returns_404(owner1, owner2, client_user):
    st = _setup_station(owner1, slug="s1")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    c = Client()
    c.force_login(owner2)
    url = reverse("sto_owner:booking_confirm", kwargs={"pk": b.pk})
    r = c.post(url)
    assert r.status_code == 404


@pytest.mark.django_db
def test_transition_rules_confirmed_in_progress_completed_and_pending_blocked(owner1, client_user):
    st = _setup_station(owner1, slug="s2")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot1 = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    slot2 = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(12, 0),
        end_time=time(13, 0),
    )
    b_ok = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot1,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.CONFIRMED,
    )
    apply_owner_booking_transition(b_ok, BookingStatus.IN_PROGRESS, owner1)
    b_ok.refresh_from_db()
    assert b_ok.status == BookingStatus.IN_PROGRESS
    apply_owner_booking_transition(b_ok, BookingStatus.COMPLETED, owner1)
    b_ok.refresh_from_db()
    assert b_ok.status == BookingStatus.COMPLETED

    b_bad = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot2,
        car_info="B",
        contact_phone="+7",
        description="d",
        status=BookingStatus.PENDING,
    )
    with pytest.raises(Http404):
        apply_owner_booking_transition(b_bad, BookingStatus.COMPLETED, owner1)

    slot3 = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(14, 0),
        end_time=time(15, 0),
    )
    b_skip = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot3,
        car_info="C",
        contact_phone="+7",
        description="d",
        status=BookingStatus.CONFIRMED,
    )
    with pytest.raises(Http404):
        apply_owner_booking_transition(b_skip, BookingStatus.COMPLETED, owner1)


@pytest.mark.django_db
def test_month_stats_excludes_canceled(owner1, client_user):
    st = _setup_station(owner1, slug="s3")
    bay = WorkBay.objects.create(station=st, name="П1")
    now = timezone.now()
    for i, status in enumerate(
        [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CANCELED]
    ):
        slot = TimeSlot.objects.create(
            bay=bay,
            date=timezone.localdate(),
            start_time=time(8 + i, 0),
            end_time=time(8 + i, 30),
        )
        b = Booking.objects.create(
            client=client_user,
            station=st,
            slot=slot,
            car_info=f"C{i}",
            contact_phone="+7",
            description="d",
            status=status,
            sto_confirm_deadline=now + timedelta(hours=1),
        )
        Booking.objects.filter(pk=b.pk).update(created_at=now)
    assert _month_stats_booking_count(owner1) == 2


@pytest.mark.django_db
def test_dashboard_requires_sto_owner(client_user):
    c = Client()
    c.force_login(client_user)
    r = c.get(reverse("sto_owner:dashboard"))
    assert r.status_code == 403


@pytest.mark.django_db
def test_dashboard_quick_slot_creates_today(owner1):
    st = _setup_station(owner1, slug="qslot-ok")
    bay = WorkBay.objects.create(station=st, name="П1")
    c = Client()
    c.force_login(owner1)
    d = date(2026, 8, 1)
    morning = timezone.make_aware(datetime.combine(d, time(9, 0)))
    with patch("django.utils.timezone.localdate", return_value=d):
        with patch("django.utils.timezone.localtime", return_value=morning):
            r = c.post(
                reverse("sto_owner:dashboard_quick_slot"),
                {"bay": str(bay.pk), "start_time": "14:00", "end_time": "15:30"},
            )
    assert r.status_code == 302
    slot = TimeSlot.objects.get(bay=bay, date=d)
    assert slot.start_time == time(14, 0)
    assert slot.end_time == time(15, 30)
    assert slot.is_available is True


@pytest.mark.django_db
def test_dashboard_quick_slot_rejects_past_start_today(owner1):
    st = _setup_station(owner1, slug="qslot-past")
    bay = WorkBay.objects.create(station=st, name="П1")
    c = Client()
    c.force_login(owner1)
    d = date(2026, 8, 2)
    afternoon = timezone.make_aware(datetime.combine(d, time(15, 0)))
    with patch("django.utils.timezone.localdate", return_value=d):
        with patch("django.utils.timezone.localtime", return_value=afternoon):
            r = c.post(
                reverse("sto_owner:dashboard_quick_slot"),
                {"bay": str(bay.pk), "start_time": "10:00", "end_time": "11:00"},
            )
    assert r.status_code == 302
    assert not TimeSlot.objects.filter(bay=bay, date=d).exists()
    r2 = c.get(reverse("sto_owner:dashboard"))
    assert "позже текущего" in r2.content.decode().casefold()


@pytest.mark.django_db
def test_dashboard_quick_slot_handles_duplicate_start(owner1):
    st = _setup_station(owner1, slug="qslot-dup")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2026, 8, 3)
    morning = timezone.make_aware(datetime.combine(d, time(8, 0)))
    TimeSlot.objects.create(
        bay=bay,
        date=d,
        start_time=time(12, 0),
        end_time=time(13, 0),
    )
    c = Client()
    c.force_login(owner1)
    with patch("django.utils.timezone.localdate", return_value=d):
        with patch("django.utils.timezone.localtime", return_value=morning):
            r = c.post(
                reverse("sto_owner:dashboard_quick_slot"),
                {"bay": str(bay.pk), "start_time": "12:00", "end_time": "13:00"},
            )
    assert r.status_code == 302
    assert TimeSlot.objects.filter(bay=bay, date=d).count() == 1
    r2 = c.get(reverse("sto_owner:dashboard"))
    assert "уже есть окно" in r2.content.decode().casefold()


@pytest.mark.django_db
def test_dashboard_quick_slot_404_for_non_sto_user(client_user):
    c = Client()
    c.force_login(client_user)
    r = c.post(reverse("sto_owner:dashboard_quick_slot"), {})
    assert r.status_code == 404


@pytest.mark.django_db
def test_complete_action_http_404_for_invalid_transition(owner1, client_user):
    st = _setup_station(owner1, slug="s4")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(15, 0),
        end_time=time(16, 0),
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
    c.force_login(owner1)
    url = reverse("sto_owner:booking_complete", kwargs={"pk": b.pk})
    r = c.post(url)
    assert r.status_code == 404


@pytest.mark.django_db
def test_owner_station_profile_get_ok(owner1):
    st = _setup_station(owner1, slug="prof-get")
    c = Client()
    c.force_login(owner1)
    url = reverse("sto_owner:station_profile", kwargs={"slug": st.slug})
    r = c.get(url)
    assert r.status_code == 200
    assert "Профиль и услуги" in r.content.decode()


@pytest.mark.django_db
def test_offer_formset_same_category_twice_invalid(owner1):
    """Две строки прайса с одной категорией не проходят валидацию (нет IntegrityError на save)."""
    st = _setup_station(owner1, slug="offer-dup")
    cat, _ = ServiceCategory.objects.get_or_create(
        slug="dup-row", defaults={"name": "Дубликат строки"}
    )
    o1 = StationServiceOffer.objects.create(
        station=st,
        category=cat,
        service_title="",
        price_from_rub=500,
        note="",
    )
    fs_empty = StationServiceOfferFormSet(instance=st)
    p = fs_empty.prefix
    max_num = fs_empty.max_num if fs_empty.max_num is not None else 40
    data = {
        f"{p}-TOTAL_FORMS": 2,
        f"{p}-INITIAL_FORMS": 1,
        f"{p}-MIN_NUM_FORMS": 0,
        f"{p}-MAX_NUM_FORMS": max_num,
        f"{p}-0-id": str(o1.pk),
        f"{p}-0-category": str(cat.pk),
        f"{p}-0-price_from_rub": "500",
        f"{p}-0-service_title": "",
        f"{p}-0-note": "",
        f"{p}-1-category": str(cat.pk),
        f"{p}-1-price_from_rub": "900",
        f"{p}-1-service_title": "",
        f"{p}-1-note": "",
    }
    fs = StationServiceOfferFormSet(data, instance=st)
    assert fs.is_valid() is False


@pytest.mark.django_db
def test_offer_formset_new_row_blocked_if_category_already_in_db(owner1):
    """Новая строка с категорией, которая уже есть в БД (без удаления старой) — ошибка формы."""
    st = _setup_station(owner1, slug="offer-db-dup")
    cat, _ = ServiceCategory.objects.get_or_create(
        slug="exists-only", defaults={"name": "Уже в базе"}
    )
    StationServiceOffer.objects.create(
        station=st,
        category=cat,
        service_title="",
        price_from_rub=300,
        note="",
    )
    fs_empty = StationServiceOfferFormSet(instance=st)
    p = fs_empty.prefix
    max_num = fs_empty.max_num if fs_empty.max_num is not None else 40
    data = {
        f"{p}-TOTAL_FORMS": 1,
        f"{p}-INITIAL_FORMS": 0,
        f"{p}-MIN_NUM_FORMS": 0,
        f"{p}-MAX_NUM_FORMS": max_num,
        f"{p}-0-category": str(cat.pk),
        f"{p}-0-price_from_rub": "400",
        f"{p}-0-service_title": "",
        f"{p}-0-note": "",
    }
    fs = StationServiceOfferFormSet(data, instance=st)
    assert fs.is_valid() is False


@pytest.mark.django_db
def test_owner_can_update_station_brands(owner1):
    st = _setup_station(owner1, slug="br-1")
    bmw, _ = CarBrand.objects.get_or_create(
        slug="bmw", defaults={"name": "BMW", "sprite_key": "bmw"}
    )
    audi, _ = CarBrand.objects.get_or_create(
        slug="audi", defaults={"name": "Audi", "sprite_key": "audi"}
    )
    c = Client()
    c.force_login(owner1)
    url = reverse("sto_owner:station_brands", kwargs={"slug": st.slug})
    r = c.post(url, data={"car_brands": [bmw.pk, audi.pk]})
    assert r.status_code in (200, 302)
    st.refresh_from_db()
    assert set(st.car_brands.values_list("slug", flat=True)) == {"bmw", "audi"}


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_owner_confirm_sends_email_to_client(mock_send, owner1, client_user):
    st = _setup_station(owner1, slug="mail-confirm")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(9, 0),
        end_time=time(10, 0),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    with TestCase.captureOnCommitCallbacks(execute=True):
        apply_owner_booking_transition(b, BookingStatus.CONFIRMED, owner1)
    mock_send.assert_called()
    assert client_user.email in mock_send.call_args.kwargs["recipient_list"]


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_owner_complete_sends_email_to_client(mock_send, owner1, client_user):
    st = _setup_station(owner1, slug="mail-done")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(11, 0),
        end_time=time(12, 0),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.IN_PROGRESS,
    )
    with TestCase.captureOnCommitCallbacks(execute=True):
        apply_owner_booking_transition(b, BookingStatus.COMPLETED, owner1)
    mock_send.assert_called()
    assert client_user.email in mock_send.call_args.kwargs["recipient_list"]


@pytest.mark.django_db
@patch("apps.bookings.mail.send_mail")
def test_owner_reject_emails_client_and_saves_reason(mock_send, owner1, client_user):
    st = _setup_station(owner1, slug="rej-mail")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(14, 0),
        end_time=time(15, 0),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    c = Client()
    c.force_login(owner1)
    url = reverse("sto_owner:booking_reject", kwargs={"pk": b.pk})
    with TestCase.captureOnCommitCallbacks(execute=True):
        r = c.post(url, {"cancel_reason": "Нет запчастей"})
    assert r.status_code == 302
    mock_send.assert_called_once()
    assert client_user.email in mock_send.call_args.kwargs["recipient_list"]
    b.refresh_from_db()
    assert b.status == BookingStatus.CANCELED
    assert b.owner_cancel_reason == "Нет запчастей"


@pytest.mark.django_db
def test_owner_reviews_list_displays_review(owner1, client_user):
    st = _setup_station(owner1, slug="rev-list")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2030, 5, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
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
    Review.objects.create(booking=b, rating=5, text="Отлично")
    c = Client()
    c.force_login(owner1)
    r = c.get(reverse("sto_owner:reviews"))
    assert r.status_code == 200
    assert "Отлично".encode() in r.content


@pytest.mark.django_db
@patch("apps.reviews.mail.send_mail")
def test_mail_sto_new_review_calls_owner(mock_send, owner1, client_user):
    from apps.reviews.mail import mail_sto_new_review

    st = _setup_station(owner1, slug="mail-rev")
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=date(2030, 6, 1),
        start_time=time(9, 0),
        end_time=time(10, 0),
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
    rev = Review.objects.create(booking=b, rating=4, text="Нормально")
    mail_sto_new_review(rev)
    mock_send.assert_called_once()
    assert owner1.email in mock_send.call_args.kwargs["recipient_list"]


@pytest.mark.django_db
def test_owner_bays_page_lists_bays(owner1):
    st = _setup_station(owner1, slug="bay-list")
    WorkBay.objects.create(station=st, name="Бокс А")
    c = Client()
    c.force_login(owner1)
    r = c.get(reverse("sto_owner:bays"))
    assert r.status_code == 200
    assert "Бокс А".encode() in r.content


@pytest.mark.django_db
def test_owner_bay_add_create(owner1):
    st = _setup_station(owner1, slug="bay-add")
    c = Client()
    c.force_login(owner1)
    r = c.post(
        reverse("sto_owner:bay_add"),
        {"station": st.pk, "name": "Подъёмник 2"},
    )
    assert r.status_code == 302
    assert WorkBay.objects.filter(station=st, name="Подъёмник 2").exists()


@pytest.mark.django_db
def test_owner_bay_delete_removes_slots_without_bookings(owner1):
    st = _setup_station(owner1, slug="bay-del-ok")
    bay = WorkBay.objects.create(station=st, name="Удалить можно")
    TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(10, 0),
        end_time=time(11, 0),
    )
    c = Client()
    c.force_login(owner1)
    r = c.post(reverse("sto_owner:bay_delete", kwargs={"pk": bay.pk}))
    assert r.status_code == 302
    assert not WorkBay.objects.filter(pk=bay.pk).exists()
    assert TimeSlot.objects.filter(bay_id=bay.pk).count() == 0


@pytest.mark.django_db
def test_owner_bay_delete_blocked_when_booking_exists(owner1, client_user):
    st = _setup_station(owner1, slug="bay-del-block")
    bay = WorkBay.objects.create(station=st, name="Busy")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time(14, 0),
        end_time=time(15, 0),
    )
    Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now() + timedelta(hours=1),
    )
    c = Client()
    c.force_login(owner1)
    r = c.post(reverse("sto_owner:bay_delete", kwargs={"pk": bay.pk}))
    assert r.status_code == 302
    assert WorkBay.objects.filter(pk=bay.pk).exists()


@pytest.mark.django_db
def test_foreign_owner_bay_delete_returns_404(owner1, owner2):
    st = _setup_station(owner1, slug="bay-foreign")
    bay = WorkBay.objects.create(station=st, name="Чужой")
    c = Client()
    c.force_login(owner2)
    r = c.post(reverse("sto_owner:bay_delete", kwargs={"pk": bay.pk}))
    assert r.status_code == 404


@pytest.mark.django_db
def test_bookings_all_upcoming_includes_pending_and_future_confirmed_only(owner1, client_user):
    """Вкладка «Все записи»: pending всегда; confirmed только если слот ещё впереди по локальному времени."""
    st = _setup_station(owner1, slug="ball-filter")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2026, 10, 5)
    morning = timezone.make_aware(datetime.combine(d, time(10, 0)))

    slot_past = TimeSlot.objects.create(bay=bay, date=d, start_time=time(8, 0), end_time=time(9, 0))
    slot_mid = TimeSlot.objects.create(bay=bay, date=d, start_time=time(9, 30), end_time=time(10, 30))
    slot_future = TimeSlot.objects.create(bay=bay, date=d, start_time=time(14, 0), end_time=time(15, 0))

    b_past_conf = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot_past,
        car_info="a",
        contact_phone="+1",
        description="",
        status=BookingStatus.CONFIRMED,
        sto_confirm_deadline=timezone.now(),
    )
    b_pending = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot_mid,
        car_info="b",
        contact_phone="+1",
        description="",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now(),
    )
    b_future_conf = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot_future,
        car_info="c",
        contact_phone="+1",
        description="",
        status=BookingStatus.CONFIRMED,
        sto_confirm_deadline=timezone.now(),
    )

    with patch("django.utils.timezone.localdate", return_value=d):
        with patch("django.utils.timezone.localtime", return_value=morning):
            ids = set(_bookings_all_upcoming_qs(owner1).values_list("pk", flat=True))

    assert b_past_conf.pk not in ids
    assert b_pending.pk in ids
    assert b_future_conf.pk in ids


@pytest.mark.django_db
def test_dashboard_bookings_all_more_returns_rows(owner1, client_user):
    st = _setup_station(owner1, slug="ball-more")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2026, 10, 6)
    for i in range(7):
        slot = TimeSlot.objects.create(
            bay=bay,
            date=d,
            start_time=time(8 + i, 0),
            end_time=time(8 + i, 30),
        )
        Booking.objects.create(
            client=client_user,
            station=st,
            slot=slot,
            car_info=f"v{i}",
            contact_phone="+1",
            description="",
            status=BookingStatus.PENDING,
            sto_confirm_deadline=timezone.now(),
        )
    c = Client()
    c.force_login(owner1)
    url = reverse("sto_owner:dashboard_bookings_all_more") + "?offset=5"
    r = c.get(url)
    assert r.status_code == 200
    body = r.content.decode()
    assert "v5" in body or "v6" in body


@pytest.mark.django_db
def test_dashboard_bookings_all_more_offset_out_of_range_404(owner1, client_user):
    st = _setup_station(owner1, slug="ball-more-404")
    bay = WorkBay.objects.create(station=st, name="П1")
    d = date(2026, 10, 7)
    slot = TimeSlot.objects.create(bay=bay, date=d, start_time=time(10, 0), end_time=time(11, 0))
    Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="x",
        contact_phone="+1",
        description="",
        status=BookingStatus.PENDING,
        sto_confirm_deadline=timezone.now(),
    )
    c = Client()
    c.force_login(owner1)
    r = c.get(reverse("sto_owner:dashboard_bookings_all_more") + "?offset=5")
    assert r.status_code == 404
