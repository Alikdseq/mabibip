"""Данные для главной страницы: агрегаты каталога, слоты, акции (фаза UI)."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot

from apps.stations.models import (
    CarBrand,
    Promotion,
    ServiceCategory,
    ServiceSection,
    ServiceStation,
    StationPhoto,
    StationServiceOffer,
)

from .constants import EXECUTOR_KIND_PRIVATE
from .selectors import (
    annotate_has_slots_today,
    annotate_has_slots_tomorrow,
    annotate_nearest_free_slot,
    annotate_station_ratings,
)

# «Горячие» услуги: слаг категории (если есть в БД — фильтр ?cat=), иначе поиск ?q=
HOT_SERVICE_TILES: list[dict[str, str]] = [
    {
        "slug": "diagnostika",
        "label": "Диагностика",
        "icon": "bi-speedometer2",
        "fallback_q": "диагностика",
    },
    {
        "slug": "to-i-obsluzhivanie",
        "label": "ТО",
        "icon": "bi-wrench-adjustable",
        "fallback_q": "ТО",
    },
    {
        "slug": "shinomontazh",
        "label": "Шиномонтаж",
        "icon": "bi-circle",
        "fallback_q": "шиномонтаж",
    },
    {
        "slug": "razval-shozhdenie",
        "label": "Развал-схождение",
        "icon": "bi-arrows-angle-expand",
        "fallback_q": "развал",
    },
    {
        "slug": "konditsioner",
        "label": "Кондиционер",
        "icon": "bi-snow",
        "fallback_q": "кондиционер авто",
    },
    {
        "slug": "elektrika",
        "label": "Электрика",
        "icon": "bi-lightning-charge",
        "fallback_q": "автоэлектрик",
    },
    {
        "slug": "moyka",
        "label": "Мойка",
        "icon": "bi-droplet",
        "fallback_q": "мойка",
    },
    {
        "slug": "deteyling",
        "label": "Детейлинг",
        "icon": "bi-stars",
        "fallback_q": "детейлинг",
    },
]

# Слаги «горячих» плиток — для расширенных title/description на лендингах (фаза D3).
HOT_SERVICE_SLUGS: frozenset[str] = frozenset(t["slug"] for t in HOT_SERVICE_TILES)

# Узкие / экспресс-услуги (подмножество слагов; попадают в блок, только если есть исполнители)
EXPRESS_CATEGORY_SLUGS: frozenset[str] = frozenset(
    {
        "diagnostika",
        "razval-shozhdenie",
        "konditsioner",
        "elektrika",
        "shinomontazh",
    }
)


def _visible_stations(today, city_label: str | None = None):
    from apps.stations.catalog_city import filter_queryset_by_visitor_city

    qs = ServiceStation.objects.visible_in_catalog(today=today)
    return filter_queryset_by_visitor_city(qs, city_label)


def _href_with_city(href: str, city_label: str | None) -> str:
    if not city_label:
        return href
    sep = "&" if "?" in href else "?"
    return f"{href}{sep}city={quote(city_label)}"


def _service_landing_href(slug: str, city_label: str | None) -> str:
    from django.urls import reverse

    return _href_with_city(reverse("landing:service_category", kwargs={"slug": slug}), city_label)


def home_car_brand_tile_groups(city_label: str | None) -> tuple[list[dict], dict | None, list[dict]]:
    """Плитки марок с главной из БД (popular 9 + 10-я, остальные в «Ещё»)."""
    popular = list(CarBrand.objects.filter(is_popular=True).order_by("sort_order", "name"))
    if popular:
        primary_src = popular[:9]
        tenth = popular[9] if len(popular) > 9 else None
        more_src = list(CarBrand.objects.filter(is_popular=False).order_by("sort_order", "name"))
    else:
        all_brands = list(CarBrand.objects.order_by("sort_order", "name"))
        primary_src = all_brands[:9]
        tenth = all_brands[9] if len(all_brands) > 9 else None
        more_src = all_brands[10:]

    def _tile(b: CarBrand) -> dict:
        stem = (b.logo_png_stem or b.sprite_key or b.slug or "").strip()
        return {
            "key": b.slug,
            "label": b.name,
            "href": _brand_landing_href(b.slug, city_label),
            "logo_stem": stem,
        }

    return [_tile(b) for b in primary_src], (_tile(tenth) if tenth else None), [_tile(b) for b in more_src]


def _brand_landing_href(slug: str, city_label: str | None) -> str:
    from django.urls import reverse

    return _href_with_city(reverse("landing:car_brand", kwargs={"slug": slug}), city_label)


def _hot_service_links(today, city_label: str | None = None) -> list[dict[str, str | int | None]]:
    tile_slugs = [t["slug"] for t in HOT_SERVICE_TILES]
    cats = {c.slug: c for c in ServiceCategory.objects.filter(slug__in=tile_slugs)}
    out: list[dict[str, str | int | None]] = []
    for tile in HOT_SERVICE_TILES:
        slug = tile["slug"]
        c = cats.get(slug)
        if c:
            out.append(
                {
                    "label": tile["label"],
                    "icon": tile["icon"],
                    "href": _service_landing_href(c.slug, city_label),
                    "kind": "category",
                    "cat_id": c.pk,
                }
            )
        else:
            q = tile.get("fallback_q") or tile["label"]
            out.append(
                {
                    "label": tile["label"],
                    "icon": tile["icon"],
                    "href": _href_with_city(f"/sto/?q={q}&entry=service", city_label),
                    "kind": "search",
                    "q": q,
                }
            )
    return out


def hot_service_links_for_catalog(city_label: str | None = None) -> list[dict[str, str | int | None]]:
    """Плитки быстрых услуг для каталога (та же логика, что на главной)."""
    return _hot_service_links(timezone.localdate(), city_label=city_label)


_SLUG_ICON: dict[str, str] = {t["slug"]: t["icon"] for t in HOT_SERVICE_TILES}


def all_service_category_tiles(today, city_label: str | None = None) -> list[dict[str, str | int | None]]:
    """Все категории услуг, по которым есть исполнители в каталоге (карточки как у «популярных»)."""
    visible = _visible_stations(today, city_label=city_label)
    qs = (
        ServiceCategory.objects.filter(stations__in=visible)
        .annotate(provider_count=Count("stations", distinct=True))
        .filter(provider_count__gt=0)
        .order_by("-provider_count", "name")
    )
    out: list[dict[str, str | int | None]] = []
    for c in qs:
        icon = _SLUG_ICON.get(c.slug, "bi-tools")
        out.append(
            {
                "label": c.name,
                "icon": icon,
                "href": _service_landing_href(c.slug, city_label),
                "kind": "category",
                "cat_id": c.pk,
            }
        )
    return out


def all_service_section_tiles(today, city_label: str | None = None) -> list[dict[str, str | int | None]]:
    """Разделы услуг, по которым есть исполнители в каталоге (кнопки на главной)."""
    visible = _visible_stations(today, city_label=city_label)
    qs = (
        ServiceSection.objects.filter(categories__stations__in=visible)
        .distinct()
        .order_by("sort_order", "name")
    )
    out: list[dict[str, str | int | None]] = []
    for s in qs:
        icon = (s.icon or "").strip() or "bi-tools"
        # Ведём на лендинг раздела (как у точечной услуги).
        href = _href_with_city(f"/razdely/{quote(s.slug)}/", city_label)
        out.append(
            {
                "label": s.name,
                "icon": icon,
                "href": href,
                "kind": "section",
                "slug": s.slug,
            }
        )
    return out


def _free_slots_window(today, *, city_label: str | None = None, limit: int = 18):
    tomorrow = today + timedelta(days=1)
    visible = _visible_stations(today, city_label=city_label)
    active_booking = Booking.objects.filter(slot_id=OuterRef("pk")).exclude(
        status=BookingStatus.CANCELED,
    )
    qs = (
        TimeSlot.objects.filter(
            date__in=[today, tomorrow],
            is_available=True,
            bay__station__in=visible,
        )
        .annotate(has_booking=Exists(active_booking))
        .filter(has_booking=False)
        .select_related("bay", "bay__station")
        .order_by("date", "start_time", "pk")
    )
    slots = []
    for slot in qs[: max(limit * 3, 40)]:
        if slot.date == today and timezone.now().date() == today:
            if timezone.now().time() > slot.start_time:
                continue
        slots.append(slot)
        if len(slots) >= limit:
            break
    return slots


def _category_provider_rows(
    today,
    *,
    city_label: str | None = None,
    slug_filter: frozenset[str] | None = None,
    limit: int = 8,
):
    visible = _visible_stations(today, city_label=city_label)
    qs = (
        ServiceCategory.objects.filter(stations__in=visible)
        .annotate(provider_count=Count("stations", distinct=True))
        .filter(provider_count__gt=0)
        .order_by("-provider_count", "name")
    )
    if slug_filter is not None:
        qs = qs.filter(slug__in=slug_filter)
    rows = []
    for c in qs[:limit]:
        rows.append(
            {
                "id": c.pk,
                "name": c.name,
                "slug": c.slug,
                "provider_count": c.provider_count,
                "catalog_url": _service_landing_href(c.slug, city_label),
            }
        )
    return rows


def build_homepage_context(city_label: str | None = None) -> dict:
    today = timezone.localdate()
    visible = _visible_stations(today, city_label=city_label)
    station_count = visible.count()

    tomorrow = today + timedelta(days=1)
    featured_qs = annotate_station_ratings(visible)
    featured_qs = annotate_has_slots_today(featured_qs, today)
    featured_qs = annotate_has_slots_tomorrow(featured_qs, tomorrow)
    featured_qs = annotate_nearest_free_slot(featured_qs, today)
    featured = list(
        featured_qs.order_by("-avg_rating", "name")
        .prefetch_related(
            "categories",
            Prefetch(
                "photos",
                queryset=StationPhoto.objects.order_by("order", "pk"),
            ),
            Prefetch(
                "service_offers",
                queryset=StationServiceOffer.objects.select_related("category").order_by(
                    "category__name",
                    "pk",
                ),
            ),
            Prefetch(
                "car_brands",
                queryset=CarBrand.objects.order_by("-is_popular", "sort_order", "name"),
            ),
        )[:6]
    )

    promotions = list(
        Promotion.objects.filter(is_active=True)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
        .select_related("station")
        .order_by("sort_order", "-created_at")[:12]
    )

    categories_with_providers = (
        ServiceCategory.objects.filter(stations__in=visible).values("pk").distinct().count()
    )

    brands_primary, brands_10th, brands_more = home_car_brand_tile_groups(city_label)
    return {
        "home_car_brands_primary": brands_primary,
        "home_car_brands_10th": brands_10th,
        "home_car_brands_more": brands_more,
        "home_station_count": station_count,
        "home_categories_count": categories_with_providers,
        "home_service_section_tiles": all_service_section_tiles(today, city_label=city_label),
        "home_featured_stations": featured,
        "home_express_categories": _category_provider_rows(
            today,
            city_label=city_label,
            slug_filter=EXPRESS_CATEGORY_SLUGS,
            limit=8,
        ),
        "home_free_slots": _free_slots_window(today, city_label=city_label, limit=18),
        "home_promotions": promotions,
        "executor_private": EXECUTOR_KIND_PRIVATE,
        "catalog_today": today,
        "catalog_has_distance": False,
        "catalog_listing": False,
        "home_today": today,
        "home_tomorrow": today + timedelta(days=1),
        **_home_feature_badges(),
    }


def _home_feature_badges() -> dict:
    from django.conf import settings

    out = {"home_help_active_count": 0, "home_problems_open_count": 0}
    if getattr(settings, "DRIVER_HELP_ENABLED", True):
        try:
            from apps.driver_help.services import active_help_count

            out["home_help_active_count"] = active_help_count()
        except Exception:
            pass
    if getattr(settings, "DRIVER_PROBLEMS_ENABLED", True):
        try:
            from apps.driver_problems.services import open_problems_count

            out["home_problems_open_count"] = open_problems_count()
        except Exception:
            pass
    return out
