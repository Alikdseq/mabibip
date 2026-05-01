"""Кэш метаданных карточки СТО (фаза F2.1.5)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache


def station_card_cache_key(station_id: int) -> str:
    return f"sto_card:{station_id}"


def get_station_card_cache(station_id: int) -> dict[str, Any] | None:
    return cache.get(station_card_cache_key(station_id))


def set_station_card_cache(station_id: int, payload: dict[str, Any]) -> None:
    cache.set(
        station_card_cache_key(station_id),
        payload,
        getattr(settings, "STATION_CARD_CACHE_TTL", 900),
    )


def invalidate_station_card(station_id: int) -> None:
    cache.delete(station_card_cache_key(station_id))
