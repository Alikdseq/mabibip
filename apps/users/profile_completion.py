# -*- coding: utf-8 -*-
"""Проверка заполненности бизнес-профиля и ссылки на редактирование."""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from apps.users.models import User

PROFILE_ADDRESS_PLACEHOLDER = "адрес уточняется после модерации"
AUTOSHOP_DESCRIPTION_MIN_LEN = 20


def registration_moderation_enabled() -> bool:
    return bool(getattr(settings, "REGISTRATION_MODERATION_ENABLED", False))


def _station_placeholder_address(address: str) -> bool:
    a = (address or "").strip().lower()
    return not a or PROFILE_ADDRESS_PLACEHOLDER in a


def station_profile_complete(station) -> bool:
    from apps.stations.models import StationServiceOffer

    if _station_placeholder_address(station.address):
        return False
    phone = (getattr(station, "contact_phone", None) or "").strip()
    owner_phone = (getattr(station.owner, "phone", None) or "").strip() if station.owner_id else ""
    if not phone and not owner_phone:
        return False
    has_categories = station.categories.exists()
    has_offers = StationServiceOffer.objects.filter(station=station).exists()
    return has_categories or has_offers


def autoshop_profile_complete(shop) -> bool:
    if not (shop.name or "").strip():
        return False
    if not (shop.city_label or "").strip():
        return False
    if len((shop.description or "").strip()) < AUTOSHOP_DESCRIPTION_MIN_LEN:
        return False
    phone = (shop.contact_phone or "").strip()
    owner_phone = (getattr(shop.owner, "phone", None) or "").strip() if shop.owner_id else ""
    return bool(phone or owner_phone)


def instructor_profile_complete(profile) -> bool:
    if not (profile.name or "").strip():
        return False
    if not (profile.city_label or "").strip():
        return False
    if len((profile.description or "").strip()) < AUTOSHOP_DESCRIPTION_MIN_LEN:
        return False
    phone = (profile.contact_phone or "").strip()
    owner_phone = (getattr(profile.owner, "phone", None) or "").strip() if profile.owner_id else ""
    if not phone and not owner_phone:
        return False
    return profile.price_per_hour is not None


def business_profile_incomplete(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "business_role", "")
    if role == User.BusinessRole.INSTRUCTOR:
        profile = getattr(user, "instructor_profile", None)
        if not profile:
            return True
        return not instructor_profile_complete(profile)
    if role == User.BusinessRole.AUTOSHOP:
        shop = getattr(user, "autoshop_profile", None)
        if not shop:
            return True
        return not autoshop_profile_complete(shop)
    if getattr(user, "is_sto_owner", False) and role in (
        User.BusinessRole.MASTER,
        User.BusinessRole.AUTOSERVICE,
    ):
        from apps.stations.models import ServiceStation

        stations = ServiceStation.objects.filter(owner=user)
        if not stations.exists():
            return True
        return any(not station_profile_complete(s) for s in stations)
    return False


def profile_edit_url(user) -> str | None:
    role = getattr(user, "business_role", "")
    if role == User.BusinessRole.INSTRUCTOR:
        return reverse("instructor_owner:profile_edit")
    if role == User.BusinessRole.AUTOSHOP:
        return reverse("shop_owner:profile_edit")
    if getattr(user, "is_sto_owner", False):
        from apps.stations.models import ServiceStation

        station = ServiceStation.objects.filter(owner=user).order_by("pk").first()
        if station:
            return reverse("sto_owner:station_profile", kwargs={"slug": station.slug})
        return reverse("sto_owner:dashboard")
    return None


def profile_completion_checklist(user) -> list[str]:
    role = getattr(user, "business_role", "")
    if role == User.BusinessRole.INSTRUCTOR:
        return [
            "Укажите имя и город",
            "Опишите услуги и опыт",
            "Укажите цену за час и телефон",
        ]
    if role == User.BusinessRole.AUTOSHOP:
        return [
            "Укажите название и город",
            "Добавьте описание магазина (не менее 20 символов)",
            "Укажите телефон для связи",
        ]
    return [
        "Укажите реальный адрес (не черновик после регистрации)",
        "Выберите услуги или добавьте прайс",
        "Проверьте телефон для клиентов",
    ]


def maybe_activate_station_after_profile_save(station) -> None:
    """Включить станцию в каталог после первого полного профиля."""
    if station.is_active:
        return
    if not station_profile_complete(station):
        return
    station.is_active = True
    station.save(update_fields=["is_active"])
