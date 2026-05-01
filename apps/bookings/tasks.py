"""Фоновые задачи бронирований (фаза F3)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.bookings.tasks.generate_weekly_slots")
def generate_weekly_slots() -> int:
    """Ежедневное пополнение слотов на горизонт SLOT_GENERATION_DAYS_AHEAD."""
    from apps.bookings.slot_generation import run_generate_weekly_slots

    n = run_generate_weekly_slots()
    logger.info("generate_weekly_slots created %s slot rows", n)
    return n


@shared_task(name="apps.bookings.tasks.expire_unconfirmed_bookings")
def expire_unconfirmed_bookings() -> int:
    """Периодическая автоотмена заявок без подтверждения СТО (см. STO_CONFIRM_DEADLINE_HOURS)."""
    from apps.bookings.services import expire_unconfirmed_bookings_now

    n = expire_unconfirmed_bookings_now()
    if n:
        logger.info("expire_unconfirmed_bookings canceled count=%s", n)
    return n


@shared_task(name="apps.bookings.tasks.send_booking_reminders_2h")
def send_booking_reminders_2h() -> int:
    """Письмо клиенту примерно за 2 ч до начала подтверждённой записи (окно под расписание beat)."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.bookings.constants import BookingStatus
    from apps.bookings.mail import mail_client_booking_reminder_2h
    from apps.bookings.models import Booking
    from apps.bookings.services import booking_slot_start_datetime

    now = timezone.now()
    win_start = now + timedelta(hours=1, minutes=50)
    win_end = now + timedelta(hours=2, minutes=10)
    qs = Booking.objects.filter(
        status=BookingStatus.CONFIRMED,
        reminder_2h_sent_at__isnull=True,
    ).select_related("client", "station", "slot")
    sent = 0
    for booking in qs:
        start = booking_slot_start_datetime(booking)
        if not (win_start <= start <= win_end):
            continue
        try:
            mail_client_booking_reminder_2h(booking)
        except Exception:
            logger.exception("send_booking_reminders_2h mail failed booking_id=%s", booking.pk)
        else:
            Booking.objects.filter(pk=booking.pk, reminder_2h_sent_at__isnull=True).update(
                reminder_2h_sent_at=now
            )
            sent += 1
    if sent:
        logger.info("send_booking_reminders_2h sent=%s", sent)
    return sent
