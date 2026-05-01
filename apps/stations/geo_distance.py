"""Расчёт расстояний на сфере (каталог СТО без привязки к конкретному SQL диалекту тестов/прода)."""

from __future__ import annotations

import math

from django.contrib.gis.geos import Point


def haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Great-circle distance между двумя точками WGS-84, километры."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    dlat = math.radians(lat2 - lat1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return r * c


def distance_km_from_point(origin_lng: float, origin_lat: float, location: Point | None) -> float | None:
    if location is None:
        return None
    return haversine_km(origin_lng, origin_lat, location.x, location.y)
