# -*- coding: utf-8 -*-

from django import template

register = template.Library()


@register.filter
def instructor_services_list(profile, limit=3):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 3
    raw = (getattr(profile, "services_text", None) or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return parts[:limit]


@register.filter
def instructor_services_all(profile):
    raw = (getattr(profile, "services_text", None) or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
