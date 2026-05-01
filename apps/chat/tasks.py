"""Фоновые задачи чатов (Celery)."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def prune_inactive_station_direct_threads() -> int:
    """
    Удаляет переписки «клиент–станция» без активности >3 суток, если у владельца СТО
    включена настройка автоочистки.
    """
    from apps.chat.models import StationDirectThread

    cutoff = timezone.now() - timedelta(days=3)

    qs = StationDirectThread.objects.filter(
        station__owner__sto_chat_auto_prune_inactive=True,
    ).filter(
        Q(last_message_at__lt=cutoff)
        | Q(last_message_at__isnull=True, created_at__lt=cutoff),
    )
    n, _ = qs.delete()
    if n:
        logger.info("prune_inactive_station_direct_threads removed %s rows", n)
    return n
