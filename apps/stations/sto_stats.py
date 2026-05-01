"""Аналитика для кабинета СТО: подписка и записи по месяцам (сценарий B2B, шаг 6)."""

from __future__ import annotations

from datetime import date, datetime, time as time_cls
from typing import Any

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking
from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation
from apps.stations.visibility import station_is_visible

_MONTHS_RU = (
    "янв.",
    "фев.",
    "мар.",
    "апр.",
    "мая",
    "июн.",
    "июл.",
    "авг.",
    "сен.",
    "окт.",
    "нояб.",
    "дек.",
)

_PLAN_TITLE_RU = {
    SUBSCRIPTION_PLAN_FREE: "Бесплатный",
    SUBSCRIPTION_PLAN_BASIC: "Базовый",
}


def subscription_rows_for_owner(owner) -> list[dict[str, Any]]:
    """По каждой станции: тариф, дата оплаты, видимость в каталоге."""
    today = timezone.localdate()
    bypass = getattr(settings, "CATALOG_BYPASS_SUBSCRIPTION", False)
    rows: list[dict[str, Any]] = []
    for st in ServiceStation.objects.filter(owner=owner).order_by("name", "pk"):
        visible = station_is_visible(st, today)
        paid = st.subscription_paid_until
        plan = st.subscription_plan
        plan_title = _PLAN_TITLE_RU.get(plan, st.get_subscription_plan_display())
        if bypass:
            status_note = (
                "Включён режим без требования оплаты подписки для показа в каталоге: "
                "видимость зависит от активного профиля и отсутствия блокировки биллинга."
            )
            needs_attention = not visible
        elif plan == SUBSCRIPTION_PLAN_FREE:
            status_note = "Тариф без проверки даты оплаты — станция в каталоге при активном аккаунте."
            needs_attention = not visible
        elif paid is None:
            status_note = "Для тарифа Basic укажите дату «оплачено до» или продлите подписку."
            needs_attention = True
        elif paid < today:
            status_note = f"Оплата по {paid.strftime('%d.%m.%Y')} — срок истёк, продлите для показа в каталоге."
            needs_attention = True
        else:
            status_note = f"Активна до {paid.strftime('%d.%m.%Y')} включительно."
            needs_attention = not visible
        rows.append(
            {
                "station_name": st.name,
                "plan_title": plan_title,
                "paid_until_display": paid.strftime("%d.%m.%Y") if paid else "—",
                "catalog_visible": visible,
                "status_note": status_note,
                "needs_attention": needs_attention,
            }
        )
    return rows


def monthly_booking_series_for_owner(owner, *, months: int = 12) -> list[dict[str, Any]]:
    """
    Число заявок по месяцам (по дате создания записи), без отменённых.
    Последние `months` месяцев, включая текущий; для графика — процент от максимума в окне.
    """
    today = timezone.localdate()
    keys: list[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()

    start_year, start_month = keys[0]
    start_day = date(start_year, start_month, 1)
    start_dt = timezone.make_aware(datetime.combine(start_day, time_cls.min))

    qs = (
        Booking.objects.filter(station__owner=owner, created_at__gte=start_dt)
        .exclude(status=BookingStatus.CANCELED)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(c=Count("pk"))
    )
    raw: dict[tuple[int, int], int] = {}
    for row in qs:
        dt = row["m"]
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        d = dt.date().replace(day=1)
        raw[(d.year, d.month)] = row["c"]

    series: list[dict[str, Any]] = []
    max_c = 0
    for y, mo in keys:
        c = raw.get((y, mo), 0)
        max_c = max(max_c, c)
        series.append(
            {
                "year": y,
                "month": mo,
                "label": f"{_MONTHS_RU[mo - 1]} {y}",
                "count": c,
            }
        )
    for row in series:
        row["pct"] = round(100 * row["count"] / max_c) if max_c else 0
    return series
