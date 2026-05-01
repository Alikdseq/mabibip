"""Единая логика видимости СТО в публичном каталоге (фаза 3.3)."""

from datetime import date

from django.conf import settings

from .constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE


def station_is_visible(station, today: date) -> bool:
    """
    Согласовано с ORM-фильтром ServiceStation.objects.visible_in_catalog(today=...).
    Basic: subscription_paid_until >= today (день включительно); NULL не проходит.
    """
    if not station.is_active:
        return False
    # Фаза F4: при провале списаний блокируем СТО для новых заявок и скрываем из каталога.
    if getattr(station, "billing_blocked_at", None) is not None:
        return False
    if getattr(settings, "CATALOG_BYPASS_SUBSCRIPTION", False):
        return True
    plan = station.subscription_plan
    if plan == SUBSCRIPTION_PLAN_FREE:
        return True
    if plan == SUBSCRIPTION_PLAN_BASIC:
        paid = station.subscription_paid_until
        return paid is not None and paid >= today
    return False


def station_accepts_online_booking(station, today: date) -> bool:
    """
    Можно ли создать заявку на странице станции /мастера.

    В тестах/проде совпадает с бизнес-логикой видимости: если Basic не оплачен и
    CATALOG_BYPASS_SUBSCRIPTION выключен — онлайн-запись недоступна.
    """
    if not station.is_active:
        return False
    if getattr(station, "billing_blocked_at", None) is not None:
        return False

    # Каталог и запись — разные правила:
    # - Basic без даты оплаты (NULL) допускаем к онлайн-записи (например, до первой оплаты),
    #   но можем скрывать из каталога.
    # - Basic с истёкшей датой оплаты — запись отключаем.
    plan = station.subscription_plan
    if plan == SUBSCRIPTION_PLAN_FREE:
        return True
    if plan == SUBSCRIPTION_PLAN_BASIC:
        paid = station.subscription_paid_until
        if paid is None:
            return True
        return paid >= today
    return False
