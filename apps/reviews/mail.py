"""Письма по отзывам (уведомление СТО о новом отзыве)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from apps.reviews.models import Review

logger = logging.getLogger(__name__)


def mail_sto_new_review(review: Review) -> None:
    """Владельцу СТО: клиент оставил отзыв после завершённого визита."""
    booking = review.booking
    station = booking.station
    owner = station.owner
    subject = f"Новый отзыв ★{review.rating} — {station.name}"
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    reviews_path = reverse("sto_owner:reviews")
    lk_url = f"{base}{reviews_path}" if base else reviews_path

    if not owner.email:
        logger.warning(
            "Владелец СТО %s без email — письмо о новом отзыве не отправлено (review %s).",
            owner.pk,
            review.pk,
        )
        return

    body = render_to_string(
        "reviews/email/sto_new_review.txt",
        {
            "review": review,
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
