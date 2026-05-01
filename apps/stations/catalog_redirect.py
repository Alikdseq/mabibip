"""Редиректы каталога на ЧПУ-лендинги (фаза C SEO)."""

from __future__ import annotations

from urllib.parse import quote

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from apps.core.seo import CATALOG_NOISE_KEYS, TRACKING_QUERY_KEYS


def service_only_redirect_target(request_get) -> tuple[str, str | None] | None:
    """
    Если в GET только service=<slug> и опционально city=, page=1, sort=relevance + UTM/шум —
    вернуть (slug, city_or_none) для 301 на /uslugi/<slug>/.
    """
    service_slug = (request_get.get("service") or "").strip()
    if not service_slug:
        return None

    city = (request_get.get("city") or "").strip() or None

    sort = (request_get.get("sort") or "").strip() or "relevance"
    if sort != "relevance":
        return None

    page_raw = (request_get.get("page") or "").strip()
    if page_raw.isdigit() and int(page_raw) > 1:
        return None

    for key in request_get.keys():
        lk = str(key).lower()
        if key in ("service", "city"):
            continue
        if lk in TRACKING_QUERY_KEYS or lk in CATALOG_NOISE_KEYS:
            continue
        if key == "sort":
            continue
        if key == "page":
            pr = (request_get.get("page") or "").strip()
            if not pr or pr == "1":
                continue
            return None
        return None

    return service_slug, city


def redirect_if_service_only_catalog(request: HttpRequest):
    target = service_only_redirect_target(request.GET)
    if not target:
        return None
    slug, city = target
    url = reverse("landing:service_category", kwargs={"slug": slug})
    if city:
        url = f"{url}?city={quote(city)}"
    return redirect(url, permanent=True)
