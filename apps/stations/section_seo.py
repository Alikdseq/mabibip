"""SEO-тексты и JSON-LD для лендингов разделов услуг."""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse

from apps.core.seo import clamp_seo_description

from .landing_seo import normalized_landing_faq
from .models import ServiceSection


def build_service_section_seo(section: ServiceSection, *, geo: str | None) -> tuple[str, str]:
    focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
    city_label = ((geo or "").strip() or focus or "").strip()
    name = section.name
    if city_label:
        title = f"{name} в {city_label} — СТО и мастера | МаБибип"
        desc = f"{name} в {city_label}: исполнители с отзывами, онлайн-запись. Выберите удобное время — МаБибип."
    else:
        title = f"{name} — запись в СТО и к мастерам | МаБибип"
        desc = f"{name}: каталог СТО и частных мастеров, отзывы, онлайн-запись на МаБибип."
    return title, clamp_seo_description(desc)


def service_section_faq_json_ld(*, request, section: ServiceSection, faq_items: list[dict[str, str]]) -> str:
    if not faq_items:
        return ""
    path = reverse("landing:service_section", kwargs={"slug": section.slug})
    url = request.build_absolute_uri(path) if request else ""
    entities = [
        {"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
        for item in faq_items
    ]
    doc: dict[str, Any] = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    if url:
        doc["url"] = url
    return json.dumps(doc, ensure_ascii=False)

