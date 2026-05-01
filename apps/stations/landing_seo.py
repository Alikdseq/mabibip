"""SEO-тексты и JSON-LD для лендингов услуг (фаза D)."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse

from apps.core.seo import clamp_seo_description

from .homepage import HOT_SERVICE_SLUGS
from .models import ServiceCategory


def normalized_landing_faq(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = (item.get("q") or item.get("question") or "").strip()
        a = (item.get("a") or item.get("answer") or "").strip()
        if q and a:
            out.append({"q": q, "a": a})
    return out


def build_service_category_seo(category: ServiceCategory, *, geo: str | None) -> tuple[str, str]:
    """
    Title и meta description для лендинга услуги.
    Для «горячих» категорий (HOT_SERVICE_SLUGS) — усиление формулировок «цены», «запись онлайн» (D3).
    """
    focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
    city_label = ((geo or "").strip() or focus or "").strip()
    is_hot = category.slug in HOT_SERVICE_SLUGS
    name = category.name

    if city_label:
        if is_hot:
            title = f"{name} в {city_label} — цены, запись онлайн | МаБибип"
            desc = (
                f"{name} в {city_label}: сравните исполнителей, ориентиры по ценам и отзывы. "
                f"Онлайн-запись без звонков — МаБибип."
            )
        else:
            title = f"{name} в {city_label} — СТО и мастера | МаБибип"
            desc = (
                f"{name} в {city_label}: исполнители с отзывами, онлайн-запись. "
                f"Выберите удобное время — МаБибип."
            )
    else:
        if is_hot:
            title = f"{name} — цены и запись в СТО онлайн | МаБибип"
            desc = (
                f"{name}: каталог СТО и мастеров, ориентиры по ценам, отзывы, онлайн-запись — МаБибип."
            )
        else:
            title = f"{name} — запись в СТО и к мастерам | МаБибип"
            desc = f"{name}: каталог СТО и частных мастеров, отзывы, онлайн-запись на МаБибип."

    return title, clamp_seo_description(desc)


def service_category_faq_json_ld(*, request, category: ServiceCategory, faq_items: list[dict[str, str]]) -> str:
    if not faq_items:
        return ""
    path = reverse("landing:service_category", kwargs={"slug": category.slug})
    url = request.build_absolute_uri(path) if request else ""
    entities = []
    for item in faq_items:
        entities.append(
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
        )
    doc = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }
    if url:
        doc["url"] = url
    return json.dumps(doc, ensure_ascii=False)
