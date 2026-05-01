"""
Геокодирование адреса через Nominatim (только фиксированный URL — защита от SSRF, документ 07 B.1).
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.gis.geos import Point

logger = logging.getLogger(__name__)

NOMINATIM_HOST = "nominatim.openstreetmap.org"
NOMINATIM_SEARCH = f"https://{NOMINATIM_HOST}/search"


def geocode_address_to_point(address: str) -> Point | None:
    """
    Возвращает Point(lng, lat, srid=4326) или None.
    Не принимает произвольный URL — только внутренний вызов Nominatim.
    """
    text = (address or "").strip()
    if not text:
        return None
    if not getattr(settings, "GEOCODING_ENABLED", False):
        return None

    params = {"q": text, "format": "json", "limit": "1"}
    url = f"{NOMINATIM_SEARCH}?{urlencode(params)}"
    if not url.startswith(f"https://{NOMINATIM_HOST}/"):
        logger.error("geocode: отклонён нестандартный host")
        return None

    headers = {"User-Agent": getattr(settings, "GEOCODING_USER_AGENT", "ProMaster/1.0")}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("geocode nominatim failed: %s", e)
        return None

    if not data:
        return None
    item = data[0]
    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return Point(lon, lat, srid=4326)
