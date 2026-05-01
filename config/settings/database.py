"""Разбор DATABASE_URL для PostgreSQL (dev/prod)."""

from __future__ import annotations

import re
from typing import Any

_POSTGRES_URL = re.compile(
    r"postgres(?:ql)?://(?P<user>[^:]+):(?P<password>[^@]+)@"
    r"(?P<host>[^:]+):(?P<port>\d+)/(?P<name>[^/?]+)",
)


def postgres_from_database_url(url: str) -> dict[str, Any] | None:
    """
    Возвращает конфиг Django DATABASES['default'] или None, если URL не подходит.
    Пароли со спецсимволами в URL нужно кодировать (%40 и т.д.).
    """
    url = (url or "").strip()
    if not url:
        return None
    m = _POSTGRES_URL.match(url)
    if not m:
        return None
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": m.group("name"),
        "USER": m.group("user"),
        "PASSWORD": m.group("password"),
        "HOST": m.group("host"),
        "PORT": m.group("port"),
    }
