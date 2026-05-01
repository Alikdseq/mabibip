"""Правила доступности слота для записи (фаза 4.1; hold Redis — фаза F3)."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.redis_holds import get_slot_hold_user_id


def slot_is_bookable(
    slot: TimeSlot,
    now: datetime | None = None,
    *,
    for_user=None,
    exclude_reschedule_for_booking_id: int | None = None,
) -> bool:
    """
    Слот можно выбрать для новой заявки, если дата не в прошлом (по календарю),
    слот не выключен владельцем, нет «живой» брони (не canceled) и нет чужого Redis-hold.
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    if slot.date < today:
        return False
    if slot.date == today:
        # Окно на сегодня: после начала интервала запись на этот слот не предлагаем.
        if slot.start_time < timezone.localtime(now).time():
            return False
    if not slot.is_available:
        return False
    holder = get_slot_hold_user_id(slot.pk)
    if holder is not None:
        if for_user is not None and getattr(for_user, "pk", None) == holder:
            pass
        else:
            return False
    # Слот «забронирован» предложением переноса другой заявкой (pending).
    held = Booking.objects.filter(
        status=BookingStatus.PENDING,
        reschedule_proposed_slot_id=slot.pk,
    )
    if exclude_reschedule_for_booking_id:
        held = held.exclude(pk=exclude_reschedule_for_booking_id)
    if held.exists():
        return False
    return not Booking.objects.filter(slot=slot).exclude(status=BookingStatus.CANCELED).exists()
