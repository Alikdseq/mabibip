from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.models import CityExpansionSignal


def record_business_city(city_label: str) -> None:
    """
    Записать сигнал «город для расширения» для бизнес-регистраций.
    Если админ ранее нажал «Отлично», при новом появлении снова поднимаем флаг (acknowledged=False).
    """
    city = (city_label or "").strip()
    if not city:
        return
    now = timezone.now()
    with transaction.atomic():
        obj, created = CityExpansionSignal.objects.select_for_update().get_or_create(
            city_label=city,
            defaults={"seen_count": 1, "acknowledged": False, "last_seen_at": now},
        )
        if not created:
            obj.seen_count = int(obj.seen_count or 0) + 1
            obj.acknowledged = False
            obj.last_seen_at = now
            obj.save(update_fields=["seen_count", "acknowledged", "last_seen_at"])

