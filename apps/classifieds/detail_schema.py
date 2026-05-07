"""JSON-LD для объявления (Offer/Product) и BreadcrumbList."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse

from .models import Ad, AdKind


def _abs(request, rel: str) -> str:
    if not rel:
        return ""
    if request:
        return request.build_absolute_uri(rel)
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    return f"{base}{rel}" if base else ""


def _ad_url(ad: Ad) -> str:
    return reverse("classifieds:ad_detail", kwargs={"pk": ad.pk})


def _ad_list_url(ad: Ad) -> str:
    if ad.kind == AdKind.CAR:
        if getattr(ad, "car_deal_type", "") == "rent":
            deal = "rent_special" if (getattr(ad, "rent_vehicle_type", "") == "special") else "rent_car"
        else:
            deal = "sale"
        return f"{reverse('classifieds:ads_list')}?tab=car&deal={deal}"
    return f"{reverse('classifieds:ads_list')}?tab=part"


def ad_detail_json_ld(ad: Ad, *, request) -> str:
    photos = list(getattr(ad, "photos", []).all()) if hasattr(ad, "photos") else []
    images = []
    for ph in photos[:8]:
        try:
            images.append(_abs(request, ph.image.url))
        except Exception:
            continue

    name = (ad.car_card_headline() if getattr(ad, "kind", "") == AdKind.CAR else (ad.title or "")).strip()
    desc = (ad.description or ad.title or "").strip()

    url = _abs(request, _ad_url(ad))
    list_url = _abs(request, _ad_list_url(ad))

    offer: dict[str, Any] | list[dict[str, Any]]
    if ad.kind == AdKind.CAR and getattr(ad, "car_deal_type", "") == "rent":
        offers: list[dict[str, Any]] = []
        if getattr(ad, "rent_price_hour_rub", None):
            offers.append(
                {
                    "@type": "Offer",
                    "price": int(ad.rent_price_hour_rub),
                    "priceCurrency": "RUB",
                    "url": url,
                    "description": "Цена аренды за час",
                    "availability": "https://schema.org/InStock",
                }
            )
        if getattr(ad, "rent_price_day_rub", None):
            offers.append(
                {
                    "@type": "Offer",
                    "price": int(ad.rent_price_day_rub),
                    "priceCurrency": "RUB",
                    "url": url,
                    "description": "Цена аренды за сутки",
                    "availability": "https://schema.org/InStock",
                }
            )
        offer = offers or {
            "@type": "Offer",
            "url": url,
            "availability": "https://schema.org/InStock",
        }
    else:
        offer = {
            "@type": "Offer",
            "price": int(getattr(ad, "price", 0) or 0),
            "priceCurrency": "RUB",
            "url": url,
            "availability": "https://schema.org/InStock",
        }

    product: dict[str, Any] = {
        "@type": "Product",
        "name": name or (ad.title or "Объявление"),
        "description": desc[:800] if desc else "",
        "url": url,
        "offers": offer,
    }
    if images:
        product["image"] = images

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": _abs(request, "/")},
            {"@type": "ListItem", "position": 2, "name": "Объявления", "item": list_url},
            {"@type": "ListItem", "position": 3, "name": (name or ad.title or "Объявление")[:60], "item": url},
        ],
    }

    doc = {"@context": "https://schema.org", "@graph": [breadcrumb, product]}
    return json.dumps(doc, ensure_ascii=False)

