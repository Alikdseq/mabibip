"""Запросы для каталога и карточки СТО (фаза 3.4)."""

from datetime import date, timedelta

from django.db.models import Avg, Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone as dj_tz

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.constants import CATALOG_DAY_RANGE


def annotate_station_ratings(qs):
    """Средний рейтинг и число отзывов: завершённые визиты, отзыв не скрыт модерацией."""
    rev_ok = Q(
        bookings__status=BookingStatus.COMPLETED,
        bookings__review__moderation_status__in=["ok", "under_review"],
    )
    return qs.annotate(
        avg_rating=Avg("bookings__review__rating", filter=rev_ok),
        review_count=Count("bookings__review", filter=rev_ok, distinct=True),
    )


def _free_slot_exists_subquery(station_outer_ref: str, day: date):
    cal_today = dj_tz.localdate(dj_tz.now())
    qs = TimeSlot.objects.filter(
        bay__station_id=OuterRef(station_outer_ref),
        date=day,
        is_available=True,
    )
    if day == cal_today:
        qs = qs.filter(start_time__gt=dj_tz.localtime(dj_tz.now()).time())
    return qs.filter(
        ~Exists(
            Booking.objects.filter(slot_id=OuterRef("pk")).exclude(
                status=BookingStatus.CANCELED,
            )
        )
    )


def annotate_has_slots_today(qs, today: date):
    """Подзапрос: есть ли сегодня свободное окно (без активной брони)."""
    slots = _free_slot_exists_subquery("pk", today)
    return qs.annotate(has_slots_today=Exists(slots))


def annotate_has_slots_tomorrow(qs, tomorrow: date):
    slots = _free_slot_exists_subquery("pk", tomorrow)
    return qs.annotate(has_slots_tomorrow=Exists(slots))


def annotate_nearest_free_slot(qs, today: date):
    """Ближайшая свободная дата/время в горизонте каталога (для сортировки и карточки)."""
    last = today + timedelta(days=CATALOG_DAY_RANGE - 1)
    active_booking = Booking.objects.filter(slot_id=OuterRef("pk")).exclude(
        status=BookingStatus.CANCELED,
    )
    cal_today = dj_tz.localdate(dj_tz.now())
    cutoff = dj_tz.localtime(dj_tz.now()).time()
    free_slots = (
        TimeSlot.objects.filter(
            bay__station_id=OuterRef("pk"),
            date__gte=today,
            date__lte=last,
            is_available=True,
        )
        .filter(Q(date__gt=cal_today) | Q(date=cal_today, start_time__gt=cutoff))
        .filter(~Exists(active_booking))
        .order_by("date", "start_time")
    )
    return qs.annotate(
        nearest_slot_date=Subquery(free_slots.values("date")[:1]),
        nearest_slot_time=Subquery(free_slots.values("start_time")[:1]),
    )


def station_has_slots_today(station_id: int, today: date) -> bool:
    """
    Есть ли свободное окно на дату: слот доступен и нет активной (не отменённой) брони.
    Для текущего календарного дня учитываются только окна, которые ещё не начались.
    """
    cal_today = dj_tz.localdate(dj_tz.now())
    qs = TimeSlot.objects.filter(
        bay__station_id=station_id,
        date=today,
        is_available=True,
    ).filter(
        ~Exists(
            Booking.objects.filter(slot_id=OuterRef("pk")).exclude(
                status=BookingStatus.CANCELED
            )
        )
    )
    if today == cal_today:
        qs = qs.filter(start_time__gt=dj_tz.localtime(dj_tz.now()).time())
    return qs.exists()
