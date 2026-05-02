"""Дополнительный контекст шаблонов."""

from __future__ import annotations

from django.conf import settings
from django.templatetags.static import static

from apps.core.seo import build_canonical_url


def map_feature_enabled(request):
    return {"MAP_FEATURE_ENABLED": getattr(settings, "MAP_FEATURE_ENABLED", False)}


def nav_badges(request):
    """Бейджи «Чаты», заявки СТО, поддержка — один расчёт на запрос (base.html раньше вызывал теги дважды)."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "nav_chats_unread_total": 0,
            "nav_sto_pending_bookings": 0,
            "nav_support_unread": 0,
        }

    from apps.bookings.constants import BookingStatus
    from apps.bookings.models import Booking
    from apps.chat.booking_inbox_services import user_unread_total_for_header
    from apps.chat.inbox_services import direct_unread_total_for_owner
    from apps.support.unread import support_unread_count_for_user
    from apps.users.models import User

    n = int(user_unread_total_for_header(user))
    if (
        getattr(user, "is_sto_owner", False)
        and getattr(user, "sto_moderation_status", None) == User.StoModerationStatus.APPROVED
    ):
        n += int(direct_unread_total_for_owner(user))

    pending = 0
    if getattr(user, "is_sto_owner", False) and getattr(user, "sto_moderation_status", "") == "approved":
        pending = int(Booking.objects.filter(station__owner=user, status=BookingStatus.PENDING).count())

    return {
        "nav_chats_unread_total": n,
        "nav_sto_pending_bookings": pending,
        "nav_support_unread": int(support_unread_count_for_user(user)),
    }


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
