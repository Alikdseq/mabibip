from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import ServiceStation

logger = logging.getLogger(__name__)


@shared_task(name="apps.stations.tasks.notify_stations_task")
def notify_stations_task(station_ids: list[int], subject: str | None = None, body: str | None = None) -> int:
    """
    F7.1.4: массовая рассылка выбранным СТО.
    Реальная интеграция (SMS/Push/Email-шаблоны) может быть добавлена позднее.
    """
    subject = subject or "[МаБибип] Уведомление"
    body = body or "У вас новое уведомление в системе МаБибип."

    qs = (
        ServiceStation.objects.filter(id__in=station_ids)
        .select_related("owner")
        .only("id", "name", "owner__email", "owner__phone")
    )

    sent = 0
    for st in qs:
        email = (getattr(st.owner, "email", None) or "").strip() if st.owner_id else ""
        if not email:
            logger.info("notify_stations_task: skip station=%s no email", st.id)
            continue
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            sent += 1
        except Exception:
            logger.exception("notify_stations_task: send failed station=%s", st.id)
    return sent

