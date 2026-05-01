"""Почтовые уведомления по бронированиям (фаза 4.6)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)


def _abs_url(path: str) -> str:
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    return f"{base}{p}" if base else p


def _client_email(booking: Booking) -> str | None:
    email = (getattr(booking.client, "email", None) or "").strip()
    return email or None


def _send_client_txt(
    booking: Booking,
    *,
    subject: str,
    template: str,
    extra: dict | None = None,
) -> None:
    to = _client_email(booking)
    if not to:
        logger.warning(
            "Клиент %s без email — письмо «%s» не отправлено (бронь %s).",
            booking.client_id,
            subject,
            booking.pk,
        )
        return
    ctx = {
        "booking": booking,
        "station": booking.station,
        "cabinet_url": _abs_url(reverse("cabinet:bookings")),
    }
    if extra:
        ctx.update(extra)
    body = render_to_string(template, ctx)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        fail_silently=False,
    )


def mail_sto_new_booking(booking: Booking, request=None) -> None:
    """Письмо владельцу СТО о новой заявке."""
    station = booking.station
    owner = station.owner
    subject = f"Новая заявка №{booking.pk} — {station.name}"

    if request is not None:
        lk_url = request.build_absolute_uri("/")
    else:
        base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
        lk_url = f"{base}/" if base else "(укажите SITE_BASE_URL или откройте из браузера)"

    if not owner.email:
        logger.warning("Владелец СТО %s без email — письмо о заявке не отправлено.", owner.pk)
        return

    body = render_to_string(
        "bookings/email/sto_new_booking.txt",
        {
            "booking": booking,
            "station": station,
            "lk_url": lk_url,
        },
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[owner.email],
        fail_silently=False,
    )


def mail_client_booking_confirmed(booking: Booking) -> None:
    """Клиент: СТО подтвердило запись."""
    subject = f"Запись подтверждена — {booking.station.name}"
    _send_client_txt(
        booking,
        subject=subject,
        template="bookings/email/client_booking_confirmed.txt",
    )


def mail_client_booking_reminder_2h(booking: Booking) -> None:
    """Напоминание за ~2 часа до начала слота."""
    subject = f"Напоминание: визит в {booking.station.name}"
    _send_client_txt(
        booking,
        subject=subject,
        template="bookings/email/client_booking_reminder_2h.txt",
    )


def mail_client_booking_completed(booking: Booking) -> None:
    """Визит завершён — ссылка на отзыв."""
    review_path = reverse("cabinet:review_create", kwargs={"booking_pk": booking.pk})
    subject = f"Визит завершён — {booking.station.name}"
    _send_client_txt(
        booking,
        subject=subject,
        template="bookings/email/client_booking_completed.txt",
        extra={"review_url": _abs_url(review_path)},
    )


def mail_client_booking_auto_canceled(booking: Booking) -> None:
    """СТО не подтвердило вовремя — слот снова свободен."""
    subject = f"Запись №{booking.pk} не подтверждена — выберите другое время"
    _send_client_txt(
        booking,
        subject=subject,
        template="bookings/email/client_booking_auto_canceled.txt",
        extra={"catalog_url": _abs_url(reverse("stations:list"))},
    )


def mail_client_booking_canceled_by_sto(booking: Booking) -> None:
    """СТО отменило активную запись (вручную из кабинета)."""
    subject = f"Запись отменена — {booking.station.name}"
    reason = (booking.owner_cancel_reason or "").strip()
    _send_client_txt(
        booking,
        subject=subject,
        template="bookings/email/client_booking_canceled_by_sto.txt",
        extra={
            "catalog_url": _abs_url(reverse("stations:list")),
            "cancel_reason": reason,
        },
    )
