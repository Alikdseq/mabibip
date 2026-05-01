"""Сборка queryset каталога СТО: фильтры и сортировки по GET-параметрам."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.db import connection
from django.db.models import F, Prefetch, Q
from django.db.models.expressions import OrderBy
from django.utils import timezone

from apps.stations.catalog_city import filter_queryset_by_visitor_city
from apps.stations.constants import CATALOG_DAY_RANGE, EXECUTOR_KIND_PRIVATE, EXECUTOR_KIND_STO
from apps.stations.models import CarBrand, ServiceCategory, ServiceStation, StationPhoto, StationServiceOffer

from .selectors import (
    annotate_has_slots_today,
    annotate_has_slots_tomorrow,
    annotate_nearest_free_slot,
    annotate_station_ratings,
)


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def build_catalog_queryset(request_get: Any, *, visitor_city_label: str | None = None) -> tuple:
    """
    Возвращает (queryset, meta) где meta — словарь контекста (флаги парсинга GET).

    Город: GET city переопределяет город из сессии (visitor_city_label), фильтр по District.city_label.
    """
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    last_day = today + timedelta(days=CATALOG_DAY_RANGE - 1)

    qs = ServiceStation.objects.visible_in_catalog(today=today)
    qs = annotate_station_ratings(qs)
    qs = annotate_has_slots_today(qs, today)
    qs = annotate_has_slots_tomorrow(qs, tomorrow)
    qs = annotate_nearest_free_slot(qs, today)

    p = request_get
    q = (p.get("q") or "").strip()
    brand_slug = (p.get("brand") or "").strip()
    section_slug = (p.get("section") or "").strip()
    exec_vals = p.getlist("exec")
    cat_ids = [c for c in p.getlist("cat") if str(c).strip().isdigit()]
    service_slug = (p.get("service") or "").strip()
    if service_slug:
        found_pk = ServiceCategory.objects.filter(slug=service_slug).values_list("pk", flat=True).first()
        if found_pk is not None:
            sid = str(found_pk)
            if sid not in cat_ids:
                cat_ids.append(sid)
    rating = (p.get("rating") or "").strip()
    slots_today = _truthy(p.get("slots_today"))
    slots_tomorrow = _truthy(p.get("slots_tomorrow"))
    verified = _truthy(p.get("verified"))
    open247 = _truthy(p.get("open247"))
    district_slug = (p.get("district") or "").strip()
    city_from_get = (p.get("city") or "").strip()
    # Город по умолчанию не фильтруем (показываем всё). Сессия влияет только на UI/выбор,
    # а фильтр включается явно через GET city.
    effective_city = city_from_get
    sort = (p.get("sort") or "relevance").strip()

    user_lat_raw = (p.get("user_lat") or "").strip()
    user_lng_raw = (p.get("user_lng") or "").strip()
    radius_raw = (p.get("radius_km") or "0").strip()

    meta = {
        "catalog_q": q,
        "catalog_brand": brand_slug,
        "catalog_brand_obj": None,
        "catalog_section": section_slug,
        "catalog_exec": exec_vals,
        "catalog_cat_ids": [int(x) for x in cat_ids],
        "catalog_rating": rating,
        "catalog_slots_today": slots_today,
        "catalog_slots_tomorrow": slots_tomorrow,
        "catalog_verified": verified,
        "catalog_open247": open247,
        "catalog_district": district_slug,
        "catalog_city": city_from_get,
        "catalog_effective_city": effective_city,
        "catalog_service_slug": service_slug,
        "catalog_sort": sort,
        "catalog_user_lat": user_lat_raw,
        "catalog_user_lng": user_lng_raw,
        "catalog_radius_km": radius_raw,
        "catalog_today": today,
        "catalog_tomorrow": tomorrow,
        "catalog_last_day": last_day,
        "catalog_amen_wifi": _truthy(p.get("amen_wifi")),
        "catalog_amen_coffee": _truthy(p.get("amen_coffee")),
        "catalog_amen_cards": _truthy(p.get("amen_cards")),
        "catalog_amen_tow": _truthy(p.get("amen_tow")),
        "catalog_amen_legal": _truthy(p.get("amen_legal")),
    }

    # --- фильтры ---
    if exec_vals:
        kinds = []
        if EXECUTOR_KIND_STO in exec_vals:
            kinds.append(EXECUTOR_KIND_STO)
        if EXECUTOR_KIND_PRIVATE in exec_vals:
            kinds.append(EXECUTOR_KIND_PRIVATE)
        if kinds:
            qs = qs.filter(executor_kind__in=kinds)

    if cat_ids:
        qs = qs.filter(categories__id__in=cat_ids).distinct()

    if section_slug:
        qs = qs.filter(
            Q(categories__section__slug=section_slug) | Q(service_sections__slug=section_slug)
        ).distinct()

    if brand_slug:
        # Основной фильтр — по связи car_brands. Если у станции ещё не заполнены марки,
        # оставляем мягкий fallback по тексту, чтобы не получить "пустой экран" на старых данных.
        brand_obj = None
        brand_name = ""
        try:
            brand_obj = (
                CarBrand.objects.filter(slug=brand_slug)
                .values("slug", "name", "sprite_key")
                .first()
            )
            brand_name = (brand_obj or {}).get("name") or ""
        except Exception:
            brand_obj = None
            brand_name = ""
        brand_name = (brand_name or "").strip()
        meta["catalog_brand_obj"] = brand_obj
        cond = Q(car_brands_all=True) | Q(car_brands__slug=brand_slug)
        if brand_name:
            cond = cond | Q(name__icontains=brand_name) | Q(description__icontains=brand_name)
        qs = qs.filter(cond).distinct()

    if slots_today:
        qs = qs.filter(has_slots_today=True)
    if slots_tomorrow:
        qs = qs.filter(has_slots_tomorrow=True)

    if verified:
        qs = qs.filter(is_verified=True)
    if open247:
        qs = qs.filter(is_open_24_7=True)

    if district_slug:
        qs = qs.filter(district__slug=district_slug)

    if effective_city:
        qs = filter_queryset_by_visitor_city(qs, effective_city)

    if _truthy(p.get("amen_wifi")):
        qs = qs.filter(amenity_wifi=True)
    if _truthy(p.get("amen_coffee")):
        qs = qs.filter(amenity_coffee=True)
    if _truthy(p.get("amen_cards")):
        qs = qs.filter(amenity_cards=True)
    if _truthy(p.get("amen_tow")):
        qs = qs.filter(amenity_tow=True)
    if _truthy(p.get("amen_legal")):
        qs = qs.filter(amenity_legal=True)

    if rating == "4":
        qs = qs.filter(avg_rating__gte=4.0)
    elif rating == "5":
        qs = qs.filter(avg_rating__gte=4.9, review_count__gte=1)

    # Гео: расстояние для сортировки и карточки; фильтр по радиусу — если radius_km > 0
    user_lat = user_lng = None
    has_distance_ann = False
    try:
        if user_lat_raw and user_lng_raw:
            user_lat = float(user_lat_raw)
            user_lng = float(user_lng_raw)
            if (-90 <= user_lat <= 90) and (-180 <= user_lng <= 180):
                ref = Point(user_lng, user_lat, srid=4326)
                qs = qs.exclude(location__isnull=True).annotate(
                    distance_m=Distance("location", ref),
                )
                has_distance_ann = True
                radius_km = float(radius_raw or "0")
                if radius_km > 0:
                    qs = qs.filter(distance_m__lte=radius_km * 1000)
    except (TypeError, ValueError):
        pass
    meta["catalog_has_distance"] = has_distance_ann

    search_rank = False
    if q:
        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

            vector = (
                SearchVector("name", weight="A", config="russian")
                + SearchVector("address", weight="B", config="russian")
                + SearchVector("description", weight="C", config="russian")
                + SearchVector("categories__name", weight="C", config="russian")
            )
            query = SearchQuery(q, config="russian", search_type="websearch")
            # Websearch/fts по-русски не даёт "частичные" совпадения по подстроке.
            # Чтобы не ломать UX (и тесты фазы F8), добавляем мягкий fallback на icontains.
            qs = qs.annotate(_rank=SearchRank(vector, query)).filter(
                Q(_rank__gt=0.01)
                | Q(name__icontains=q)
                | Q(address__icontains=q)
                | Q(description__icontains=q)
                | Q(categories__name__icontains=q)
            ).distinct()
            search_rank = True
        else:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(address__icontains=q)
                | Q(description__icontains=q)
                | Q(categories__name__icontains=q)
            ).distinct()

    qs = qs.select_related("district").prefetch_related(
        Prefetch(
            "photos",
            queryset=StationPhoto.objects.order_by("order", "pk"),
        ),
        Prefetch(
            "service_offers",
            queryset=StationServiceOffer.objects.select_related("category").order_by(
                "price_from_rub",
            ),
        ),
        Prefetch(
            "car_brands",
            queryset=CarBrand.objects.order_by("-is_popular", "sort_order", "name"),
        ),
        "categories",
    )

    # --- сортировка (после аннотаций distance_m при гео) ---
    if sort == "rating":
        qs = qs.order_by(
            OrderBy(F("avg_rating"), descending=True, nulls_last=True),
            OrderBy(F("review_count"), descending=True, nulls_last=True),
            "name",
        )
    elif sort == "distance" and has_distance_ann:
        qs = qs.order_by(F("distance_m").asc(nulls_last=True), "name")
    elif sort == "distance":
        qs = qs.order_by(
            OrderBy(F("review_count"), descending=True, nulls_last=True),
            OrderBy(F("avg_rating"), descending=True, nulls_last=True),
            "name",
        )
    elif sort == "next_slot":
        qs = qs.order_by(
            OrderBy(F("nearest_slot_date"), descending=False, nulls_last=True),
            OrderBy(F("nearest_slot_time"), descending=False, nulls_last=True),
            "name",
        )
    else:
        # relevance / default
        if search_rank:
            qs = qs.order_by(
                "-_rank",
                OrderBy(F("review_count"), descending=True, nulls_last=True),
                OrderBy(F("avg_rating"), descending=True, nulls_last=True),
                "name",
            )
        else:
            qs = qs.order_by(
                OrderBy(F("review_count"), descending=True, nulls_last=True),
                OrderBy(F("avg_rating"), descending=True, nulls_last=True),
                "name",
            )

    return qs, meta
