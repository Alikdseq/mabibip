"""Отображение профиля СТО / мастера на публичной странице."""

from __future__ import annotations

from apps.stations.constants import (
    ADDRESS_PUBLIC_AFTER_BOOKING,
    ADDRESS_PUBLIC_DISTRICT,
    ADDRESS_PUBLIC_FULL,
)
from apps.stations.models import ServiceStation


def format_public_address(station: ServiceStation) -> str:
    mode = getattr(station, "address_public_mode", None) or ADDRESS_PUBLIC_FULL
    if mode == ADDRESS_PUBLIC_DISTRICT:
        if station.district_id:
            parts = [station.district.city_label or "", station.district.name]
            return "Район: " + ", ".join(p for p in parts if p).strip() or station.address
        return station.address
    if mode == ADDRESS_PUBLIC_AFTER_BOOKING:
        return "Точный адрес сообщим после подтверждения записи"
    return station.address


def station_contact_phone_e164(station: ServiceStation) -> str:
    # Мастер автосервиса: контакты всегда ведут в автосервис-родитель.
    parent = getattr(station, "parent_station", None)
    if parent is not None:
        return station_contact_phone_e164(parent)
    raw = (getattr(station, "contact_phone", None) or "").strip()
    if raw:
        return raw
    return (station.owner.phone or "").strip()


def mask_phone_e164(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) < 6:
        return "••• ••• •• ••"
    return f"{p[:4]} ••• ••• ••{p[-2:]}"


def whatsapp_href(phone_e164: str) -> str:
    digits = "".join(c for c in phone_e164 if c.isdigit())
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if not digits:
        return ""
    return f"https://wa.me/{digits}"


def telegram_href(username: str) -> str:
    u = (username or "").strip().lstrip("@")
    if not u:
        return ""
    return f"https://t.me/{u}"


def map_links_wgs84(location) -> tuple[str, str] | tuple[None, None]:
    """Ссылки на Яндекс и Google карт (Point srid=4326: x=lon, y=lat)."""
    if location is None:
        return None, None
    lon = float(location.x)
    lat = float(location.y)
    yandex = f"https://yandex.ru/maps/?ll={lon}%2C{lat}&pt={lon}%2C{lat}&z=16&l=map"
    google = f"https://www.google.com/maps?q={lat}%2C{lon}"
    return yandex, google


def review_client_public_name(booking) -> str:
    """Имя и первая буква фамилии; иначе нейтральная подпись."""
    u = booking.client
    first = (getattr(u, "first_name", None) or "").strip()
    last = (getattr(u, "last_name", None) or "").strip()
    if first and last:
        return f"{first} {last[0]}."
    if first:
        return first
    phone = (getattr(u, "phone", None) or "").strip()
    if len(phone) >= 4:
        return f"Клиент ••{phone[-2:]}"
    return "Клиент"
