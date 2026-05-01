from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count
from django.utils import timezone

from apps.reviews.models import ModerationStatus, Review

logger = logging.getLogger(__name__)


@shared_task(name="apps.reviews.tasks.detect_review_anomalies")
def detect_review_anomalies() -> list[int]:
    """
    F6.1.4: новые СТО с >5 оценок 5★ от новых пользователей за сутки.

    Реализация:
    - окно: последние 24 часа
    - новая СТО: создана не позже N дней назад (по умолчанию 30)
    - новый пользователь: date_joined не позже 1 дня назад
    - считаем distinct пользователей (не даём одному накрутить счётчик)
    """
    now = timezone.now()
    window_hours = int(getattr(settings, "REVIEW_ANOMALY_WINDOW_HOURS", 24))
    station_age_days = int(getattr(settings, "REVIEW_ANOMALY_STATION_AGE_DAYS", 30))
    new_user_days = int(getattr(settings, "REVIEW_ANOMALY_NEW_USER_AGE_DAYS", 1))
    min_cnt = int(getattr(settings, "REVIEW_ANOMALY_MIN_FIVE_STARS", 5))

    since = now - timedelta(hours=window_hours)
    station_since = now - timedelta(days=station_age_days)
    user_since = now - timedelta(days=new_user_days)

    rows = (
        Review.objects.filter(
            created_at__gte=since,
            rating=5,
            moderation_status=ModerationStatus.OK,
            booking__station__created_at__gte=station_since,
            booking__client__date_joined__gte=user_since,
        )
        .values("booking__station_id")
        .annotate(cnt=Count("booking__client_id", distinct=True))
        .filter(cnt__gt=min_cnt)
        .order_by("-cnt")
    )
    station_ids = [r["booking__station_id"] for r in rows]
    if not station_ids:
        return []

    subj = "[МаБибип] Аномалии отзывов (возможная накрутка)"
    body = "Подозрительные СТО (station_id): " + ", ".join(map(str, station_ids))

    recipients = [email for _, email in getattr(settings, "ADMINS", []) if email]
    if recipients:
        try:
            send_mail(subj, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
        except Exception:
            logger.exception("detect_review_anomalies send_mail failed")
    else:
        logger.warning("detect_review_anomalies: %s", body)

    return station_ids

