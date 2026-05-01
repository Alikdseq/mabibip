"""Дополнительный контекст шаблонов."""

from __future__ import annotations

from django.conf import settings
from django.templatetags.static import static

from apps.core.seo import build_canonical_url


def map_feature_enabled(request):
    return {"MAP_FEATURE_ENABLED": getattr(settings, "MAP_FEATURE_ENABLED", False)}


def seo_canonical(request):
    """Canonical и запасное OG-изображение (статический ассет бренда)."""
    default_img = ""
    try:
        default_img = request.build_absolute_uri(static("pm-brand-sprite.svg"))
    except Exception:
        pass
    return {
        "canonical_url": build_canonical_url(request),
        "seo_og_image_default": default_img,
    }


def erp_city_expansion_banner(request):
    """
    ERP-индикатор: в каких городах бизнес начал регистрироваться (для расширения).
    Показываем только в /secure-erp/ и только суперюзеру.
    """
    try:
        if not (request.path or "").startswith("/secure-erp/"):
            return {}
        u = getattr(request, "user", None)
        if not (u and u.is_authenticated and getattr(u, "is_superuser", False)):
            return {}
        from apps.core.models import CityExpansionSignal

        qs = CityExpansionSignal.objects.filter(acknowledged=False).order_by("-last_seen_at", "city_label")
        items = list(qs[:8])
        return {
            "erp_city_signals": items,
            "erp_city_signals_count": int(qs.count()),
        }
    except Exception:
        return {}
