"""JSON-LD для карточки исполнителя (AutoRepair / Person) и BreadcrumbList."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse

from apps.stations.constants import ADDRESS_PUBLIC_AFTER_BOOKING, EXECUTOR_KIND_PRIVATE
from apps.stations.display import format_public_address, station_contact_phone_e164
from apps.stations.models import ServiceStation


def _absolute_url(request, rel: str) -> str:
    if not rel:
        return ""
    if request:
        return request.build_absolute_uri(rel)
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    return f"{base}{rel}" if base else ""


def _station_page_path(station: ServiceStation) -> str:
    return reverse("stations:detail", kwargs={"slug": station.slug})


def station_primary_image_url(station: ServiceStation, *, request) -> str:
    for photo in station.photos.all():
        if not photo.is_work_sample and photo.image:
            return _absolute_url(request, photo.image.url)
    if station.avatar:
        return _absolute_url(request, station.avatar.url)
    return ""


def _entity_node(station: ServiceStation, *, request) -> dict[str, Any]:
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    path = _station_page_path(station)
    url = _absolute_url(request, path) if request else (f"{base}{path}" if base else "")

    avg = getattr(station, "avg_rating", None)
    rating_val: float | None = float(avg) if avg is not None else None
    rev_count = int(getattr(station, "review_count", 0) or 0)

    addr = format_public_address(station)
    phone = station_contact_phone_e164(station).strip()
    schedule = (station.work_schedule_text or "").strip()

    desc_parts: list[str] = []
    main_desc = (station.description_short or station.description or "").strip()
    if main_desc:
        desc_parts.append(main_desc[:450])
    if schedule:
        desc_parts.append(f"График: {schedule[:200]}")
    description = " ".join(desc_parts)[:500]

    image_url = station_primary_image_url(station, request=request)

    payload: dict[str, Any]
    if station.executor_kind == EXECUTOR_KIND_PRIVATE:
        payload = {
            "@type": "Person",
            "name": station.name,
            "description": description,
            "url": url,
        }
        if addr:
            payload["jobTitle"] = (station.tagline or "").strip() or "Частный автомастер"
        if image_url:
            payload["image"] = image_url
    else:
        payload = {
            "@type": "AutoRepair",
            "name": station.name,
            "description": description,
            "url": url,
        }
        if addr:
            payload["address"] = {"@type": "PostalAddress", "streetAddress": addr}
        if image_url:
            payload["image"] = image_url

    if phone:
        payload["telephone"] = phone

    if station.location is not None and station.address_public_mode != ADDRESS_PUBLIC_AFTER_BOOKING:
        payload["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(station.location.y),
            "longitude": float(station.location.x),
        }

    if rating_val is not None and rev_count > 0:
        payload["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(rating_val, 1),
            "reviewCount": rev_count,
            "bestRating": 5,
            "worstRating": 1,
        }

    return payload


def _breadcrumb_node(station: ServiceStation, *, request) -> dict[str, Any]:
    home = _absolute_url(request, "/")
    catalog = _absolute_url(request, reverse("stations:list"))
    self_url = _absolute_url(request, _station_page_path(station))
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Главная",
                "item": home,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Каталог СТО",
                "item": catalog,
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": station.name,
                "item": self_url,
            },
        ],
    }


def station_detail_json_ld(station: ServiceStation, *, request) -> str:
    """Один script: @graph с BreadcrumbList и сущностью исполнителя."""
    graph: list[dict[str, Any]] = [
        _breadcrumb_node(station, request=request),
        _entity_node(station, request=request),
    ]
    doc = {"@context": "https://schema.org", "@graph": graph}
    return json.dumps(doc, ensure_ascii=False)
