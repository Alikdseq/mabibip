"""Идемпотентная генерация слотов по шаблону WorkingHours (фаза F3).

Дополнительно: автозаполнение базового расписания 10:00–18:00 (шаг 60 мин),
если у поста нет WorkingHours. Это нужно, чтобы слоты появлялись "сразу из коробки",
а владелец мог вручную закрывать лишние окна в календаре.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from django.db import IntegrityError
from django.utils import timezone

from apps.bookings.models import TimeSlot, WorkingHours
from apps.stations.models import WorkBay

logger = logging.getLogger(__name__)

DEFAULT_OPENS_AT = time(10, 0)
DEFAULT_CLOSES_AT = time(18, 0)
DEFAULT_SLOT_MINUTES = 60


def _combine(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=None)


def _break_intervals(day: date, breaks_raw: list | None) -> list[tuple[datetime, datetime]]:
    if not breaks_raw:
        return []
    out: list[tuple[datetime, datetime]] = []
    for item in breaks_raw:
        if not isinstance(item, dict):
            continue
        try:
            hs, ms = map(int, str(item["start"]).split(":"))
            he, me = map(int, str(item["end"]).split(":"))
        except (KeyError, ValueError):
            continue
        out.append(
            (
                datetime.combine(day, time(hs, ms)),
                datetime.combine(day, time(he, me)),
            )
        )
    return out


def _overlaps_break(slot_start: datetime, slot_end: datetime, breaks: list[tuple[datetime, datetime]]) -> bool:
    for b0, b1 in breaks:
        if slot_start < b1 and slot_end > b0:
            return True
    return False


def iter_slot_times_for_day(day: date, wh: WorkingHours) -> list[tuple[time, time]]:
    """Список (start_time, end_time) для одного поста и календарного дня."""
    opens = wh.opens_at
    closes = wh.closes_at
    step = wh.slot_duration_minutes
    breaks = _break_intervals(day, wh.breaks)

    open_dt = _combine(day, opens)
    close_dt = _combine(day, closes)
    if open_dt >= close_dt:
        return []

    out: list[tuple[time, time]] = []
    cur = open_dt
    while True:
        nxt = cur + timedelta(minutes=step)
        if nxt > close_dt:
            break
        if _overlaps_break(cur, nxt, breaks):
            cur = nxt
            continue
        out.append((cur.time(), nxt.time()))
        cur = nxt
    return out


def create_slots_for_bay_day(bay: WorkBay, day: date, wh: WorkingHours) -> int:
    """Создаёт недостающие слоты; возвращает число новых строк."""
    created = 0
    for start_t, end_t in iter_slot_times_for_day(day, wh):
        try:
            _, was_created = TimeSlot.objects.get_or_create(
                bay=bay,
                date=day,
                start_time=start_t,
                defaults={
                    "end_time": end_t,
                    "is_available": True,
                },
            )
        except IntegrityError:
            logger.debug(
                "slot_generation race get_or_create bay=%s day=%s start=%s",
                bay.pk,
                day,
                start_t,
            )
            continue
        if was_created:
            created += 1
    return created


def ensure_default_working_hours_for_bay(bay: WorkBay) -> int:
    """
    Гарантирует наличие WorkingHours для всех дней недели у поста.
    Создаёт недостающие записи с дефолтом 10:00–18:00, шаг 60 минут.

    Возвращает количество созданных строк.
    """
    created = 0
    for wd in range(7):
        wh, was_created = WorkingHours.objects.get_or_create(
            bay=bay,
            weekday=wd,
            defaults={
                "opens_at": DEFAULT_OPENS_AT,
                "closes_at": DEFAULT_CLOSES_AT,
                "slot_duration_minutes": DEFAULT_SLOT_MINUTES,
                "breaks": [],
            },
        )
        if was_created:
            created += 1
        else:
            # Если расписание уже есть — не трогаем (владелец мог настроить своё).
            continue
    return created


def ensure_default_working_hours_for_station(station_id: int) -> int:
    """Создаёт дефолтные WorkingHours для всех постов станции (идемпотентно)."""
    from apps.stations.models import WorkBay

    total = 0
    for bay in WorkBay.objects.filter(station_id=station_id).order_by("pk"):
        total += ensure_default_working_hours_for_bay(bay)
    return total


def run_generate_slots_for_station(
    *,
    station_id: int,
    today: date | None = None,
    days_ahead: int | None = None,
) -> int:
    """
    Создаёт слоты на горизонт [today .. today+days_ahead] для конкретной станции.
    Если у постов нет WorkingHours — сначала создаёт дефолт 10:00–18:00, шаг 60 мин.
    """
    from datetime import timedelta
    from django.conf import settings
    from apps.stations.models import WorkBay

    today = today or timezone.localdate()
    if days_ahead is None:
        days_ahead = int(getattr(settings, "SLOT_GENERATION_DAYS_AHEAD", 14))

    ensure_default_working_hours_for_station(station_id)

    total = 0
    bays = list(WorkBay.objects.filter(station_id=station_id).order_by("pk"))
    if not bays:
        return 0

    wh_qs = WorkingHours.objects.filter(bay__in=bays).select_related("bay").order_by("bay_id", "weekday")
    wh_by_bay: dict[int, list[WorkingHours]] = {}
    for wh in wh_qs:
        wh_by_bay.setdefault(wh.bay_id, []).append(wh)

    for bay in bays:
        wh_list = wh_by_bay.get(bay.pk) or []
        if not wh_list:
            # на всякий случай (если бай появился между ensure и query)
            ensure_default_working_hours_for_bay(bay)
            wh_list = list(WorkingHours.objects.filter(bay=bay).order_by("weekday"))
        for offset in range(days_ahead + 1):
            d = today + timedelta(days=offset)
            wd = d.weekday()
            for wh in wh_list:
                if wh.weekday == wd:
                    total += create_slots_for_bay_day(bay, d, wh)
                    break
    return total


def run_generate_weekly_slots(*, today: date | None = None, days_ahead: int | None = None) -> int:
    """
    Для всех постов с расписанием создаёт слоты на горизонт [today .. today+days_ahead] включительно.
    Идемпотентно: повторный запуск не дублирует (bay, date, start_time).
    """
    from django.conf import settings

    today = today or timezone.localdate()
    if days_ahead is None:
        days_ahead = int(getattr(settings, "SLOT_GENERATION_DAYS_AHEAD", 7))

    total = 0
    qs = WorkingHours.objects.select_related("bay", "bay__station").order_by("bay_id", "weekday")
    wh_by_bay: dict[int, list[WorkingHours]] = {}
    for wh in qs:
        wh_by_bay.setdefault(wh.bay_id, []).append(wh)

    for bay_id, wh_list in wh_by_bay.items():
        bay = wh_list[0].bay
        for offset in range(days_ahead + 1):
            d = today + timedelta(days=offset)
            wd = d.weekday()
            for wh in wh_list:
                if wh.weekday != wd:
                    continue
                total += create_slots_for_bay_day(bay, d, wh)
    return total
