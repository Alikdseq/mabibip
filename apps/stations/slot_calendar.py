"""Календарь слотов СТО: неделя, группировка по дням."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.db.models import Prefetch

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.models import ServiceStation


def monday_of_week(day: date) -> date:
    """Понедельник ISO-недели для любой даты."""
    return day - timedelta(days=day.weekday())


def build_week_calendar_context(
    *,
    station: ServiceStation,
    anchor_date: date,
    owner_stations,
) -> dict[str, Any]:
    """
    Слоты станции на 7 дней с понедельника недели anchor_date.
    У каждого слота: active_booking (первая неотменённая бронь) или None.
    """
    monday = monday_of_week(anchor_date)
    sunday = monday + timedelta(days=6)

    qs = (
        TimeSlot.objects.filter(bay__station=station, date__gte=monday, date__lte=sunday)
        .select_related("bay")
        .prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.exclude(status=BookingStatus.CANCELED)
                .select_related("client")
                .order_by("pk"),
            )
        )
        .order_by("date", "start_time", "bay_id", "pk")
    )
    slots_list = list(qs)
    for s in slots_list:
        bl = list(s.bookings.all())
        s.active_booking = bl[0] if bl else None

    by_day: dict[date, list[TimeSlot]] = defaultdict(list)
    for s in slots_list:
        by_day[s.date].append(s)

    week_days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        day_slots = by_day.get(d, [])
        week_days.append({"date": d, "slots": day_slots})

    prev_week = monday - timedelta(days=7)
    next_week = monday + timedelta(days=7)

    return {
        "station": station,
        "stations_sidebar": owner_stations,
        "week_monday": monday,
        "week_sunday": sunday,
        "week_days": week_days,
        "prev_week_monday": prev_week,
        "next_week_monday": next_week,
        "anchor_date": anchor_date,
    }
