"""Отбор СТО в радиусе от точки (видимые в каталоге, с координатами)."""

from __future__ import annotations

from django.utils import timezone

from apps.stations.geo_distance import distance_km_from_point
from apps.stations.models import ServiceStation


def list_nearby_stations(
    *,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int,
    offset: int,
) -> tuple[list[tuple[ServiceStation, float]], int]:
    """
    Возвращает (срез страницы списка (станция, distance_km), всего подходящих).
    Сортировка по возрастанию расстояния.
    """
    today = timezone.localdate()
    qs = (
        ServiceStation.objects.visible_in_catalog(today=today)
        .exclude(location__isnull=True)
        .select_related("owner")
        .order_by("pk")
    )
    matched: list[tuple[ServiceStation, float]] = []
    for st in qs.iterator():
        d = distance_km_from_point(lng, lat, st.location)
        if d is not None and d <= radius_km:
            matched.append((st, round(d, 3)))
    matched.sort(key=lambda x: x[1])
    total = len(matched)
    page = matched[offset : offset + limit]
    return page, total
