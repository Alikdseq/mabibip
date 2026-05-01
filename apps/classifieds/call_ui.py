"""Контакты в объявлениях: прямой номер и режим «подменный номер» (как на крупных площадках).

Реальная переадресация звонка на телефон продавца делается на стороне АТС / облачной телефонии
(Twilio Proxy, Mango, UIS и т.д.): платформа отдаёт покупателю один публичный номер и добавочный,
а по входящему вы настраиваете маршрутизацию на номер из карточки объявления.
"""

from __future__ import annotations

from typing import Any

import phonenumbers
from django.conf import settings
from phonenumbers import PhoneNumberFormat

from apps.stations.display import mask_phone_e164
from apps.users.phone_utils import PhoneValidationError, normalize_to_e164

from .models import Ad, AdCallProxy


def seller_phone_e164(ad: Ad) -> str | None:
    raw = ""
    if ad.shop_id:
        raw = (ad.shop.contact_phone or "").strip()
    if not raw:
        raw = (getattr(ad.owner, "phone", None) or "").strip()
    if not raw:
        return None
    try:
        return normalize_to_e164(raw)
    except PhoneValidationError:
        if raw.startswith("+"):
            return raw
        return None


def format_phone_human(e164: str | None) -> str:
    if not e164:
        return "—"
    try:
        num = phonenumbers.parse(e164, None)
        return phonenumbers.format_number(num, PhoneNumberFormat.INTERNATIONAL)
    except Exception:
        return e164


def _get_or_create_extension(ad: Ad) -> str:
    obj, _created = AdCallProxy.objects.get_or_create(ad=ad)
    if not obj.extension:
        obj.assign_extension()
    return obj.extension


def build_ad_call_context(*, request, ad: Ad) -> dict[str, Any]:
    seller = seller_phone_e164(ad)
    proxy_on = bool(getattr(settings, "CLASSIFIEDS_PROXY_CALL_ENABLED", False))
    proxy_raw = (getattr(settings, "CLASSIFIEDS_PROXY_PUBLIC_PHONE_E164", "") or "").strip()
    proxy_e164: str | None = None
    if proxy_raw:
        try:
            proxy_e164 = normalize_to_e164(proxy_raw)
        except PhoneValidationError:
            proxy_e164 = proxy_raw if proxy_raw.startswith("+") else None

    is_owner = request.user.is_authenticated and request.user.pk == ad.owner_id

    if not request.user.is_authenticated:
        return {
            "authenticated": False,
            "seller_masked": mask_phone_e164(seller or "+70000000000"),
            "mode": "login",
        }

    if is_owner:
        return {
            "authenticated": True,
            "is_owner": True,
            "mode": "owner_preview",
            "seller_e164": seller,
            "seller_display": format_phone_human(seller),
            "proxy_enabled": proxy_on and bool(proxy_e164),
        }

    if proxy_on and proxy_e164:
        ext = _get_or_create_extension(ad)
        main_digits = phonenumbers.parse(proxy_e164, None)
        main_e164 = phonenumbers.format_number(main_digits, PhoneNumberFormat.E164)
        tel_href = f"tel:{main_e164},{ext}"
        return {
            "authenticated": True,
            "is_owner": False,
            "mode": "proxy",
            "proxy_e164": proxy_e164,
            "proxy_display": format_phone_human(proxy_e164),
            "extension": ext,
            "tel_href": tel_href,
        }

    return {
        "authenticated": True,
        "is_owner": False,
        "mode": "direct",
        "seller_e164": seller,
        "seller_display": format_phone_human(seller),
        "tel_href": f"tel:{seller}" if seller else "",
    }
