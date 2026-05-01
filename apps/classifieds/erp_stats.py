"""Агрегаты по объявлениям для ERP (суммарно по платформе, разбивка запчасти / авто)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.chat.models import AdDirectThread

from .models import Ad, AdCallClickEvent, AdKind, FavoriteAd


def _local_today_bounds():
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _counts_part_car_total(rows: list[tuple[str, int]]) -> dict[str, int]:
    m = dict(rows)
    p = int(m.get(AdKind.PART, 0))
    c = int(m.get(AdKind.CAR, 0))
    return {"part": p, "car": c, "total": p + c}


def platform_classifieds_stats_context() -> dict:
    start, end = _local_today_bounds()
    today_date = start.date()

    ads_published_today = Ad.objects.filter(
        is_published=True,
        created_at__gte=start,
        created_at__lt=end,
    )
    row_ads_today = list(ads_published_today.values("kind").annotate(n=Count("id")).values_list("kind", "n"))

    ads_active = Ad.objects.filter(is_published=True)
    row_ads_active = list(ads_active.values("kind").annotate(n=Count("id")).values_list("kind", "n"))

    fav_total = list(FavoriteAd.objects.values("ad__kind").annotate(n=Count("id")).values_list("ad__kind", "n"))
    fav_today = FavoriteAd.objects.filter(created_at__gte=start, created_at__lt=end)
    row_fav_today = list(fav_today.values("ad__kind").annotate(n=Count("id")).values_list("ad__kind", "n"))

    thr_total = list(AdDirectThread.objects.values("ad__kind").annotate(n=Count("id")).values_list("ad__kind", "n"))
    thr_today = AdDirectThread.objects.filter(created_at__gte=start, created_at__lt=end)
    row_thr_today = list(thr_today.values("ad__kind").annotate(n=Count("id")).values_list("ad__kind", "n"))

    clk_total = list(AdCallClickEvent.objects.values("ad_kind").annotate(n=Count("id")).values_list("ad_kind", "n"))
    clk_today = AdCallClickEvent.objects.filter(created_at__gte=start, created_at__lt=end)
    row_clk_today = list(clk_today.values("ad_kind").annotate(n=Count("id")).values_list("ad_kind", "n"))

    return {
        "classifieds_stats_today": today_date,
        "ads_published_today": _counts_part_car_total(row_ads_today),
        "ads_active_published": _counts_part_car_total(row_ads_active),
        "favorites_total": _counts_part_car_total(fav_total),
        "favorites_today": _counts_part_car_total(row_fav_today),
        "threads_total": _counts_part_car_total(thr_total),
        "threads_today": _counts_part_car_total(row_thr_today),
        "call_clicks_total": _counts_part_car_total(clk_total),
        "call_clicks_today": _counts_part_car_total(row_clk_today),
    }
