"""PostgreSQL + PostGIS (фаза F2)."""

from __future__ import annotations

from typing import Any

from .database import postgres_from_database_url


def postgres_gis_from_database_url(url: str) -> dict[str, Any] | None:
    """Как postgres_from_database_url, но движок GeoDjango PostGIS."""
    cfg = postgres_from_database_url(url)
    if not cfg:
        return None
    return {**cfg, "ENGINE": "django.contrib.gis.db.backends.postgis"}
