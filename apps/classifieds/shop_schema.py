"""JSON-LD для страницы автомагазина/разборки/автосалона (LocalBusiness) и BreadcrumbList."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse

from .models import AutoShopProfile


def _abs(request, rel: str) -> str:
    if not rel:
        return ""
    if request:
        return request.build_absolute_uri(rel)
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    return f"{base}{rel}" if base else ""


def shop_detail_json_ld(shop: AutoShopProfile, *, request) -> str:
    url = _abs(request, reverse("classifieds:shop_detail", kwargs={"slug": shop.slug}))
    shops_list = _abs(request, reverse("classifieds:shops_list"))

    kind = (shop.kind or "").strip()
    type_map = {
        "shop": "Store",
        "dismantle": "AutoPartsStore",
        "dealer": "AutoDealer",
    }
    shop_type = type_map.get(kind, "Store")

    addr = " ".join([p for p in [shop.city_label, shop.address] if (p or "").strip()]).strip()
    phone = (shop.contact_phone or "").strip()

    entity: dict[str, Any] = {
        "@type": shop_type,
        "name": shop.name,
        "url": url,
    }
    desc = (shop.description or "").strip()
    if desc:
        entity["description"] = desc[:700]
    if phone:
        entity["telephone"] = phone
    if addr:
        entity["address"] = {"@type": "PostalAddress", "streetAddress": addr}
    if shop.location is not None:
        entity["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(shop.location.y),
            "longitude": float(shop.location.x),
        }

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": _abs(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "Магазины", "item": shops_list},
            {"@type": "ListItem", "position": 3, "name": shop.name, "item": url},
        ],
    }

    doc = {"@context": "https://schema.org", "@graph": [breadcrumb, entity]}
    return json.dumps(doc, ensure_ascii=False)

