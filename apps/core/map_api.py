"""Публичное API карты: СТО/мастера/автомагазины в bbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.classifieds.models import Ad, AutoShopProfile
from apps.stations.constants import EXECUTOR_KIND_PRIVATE, EXECUTOR_KIND_STO
from apps.stations.models import CarBrand, ServiceStation


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        return None
    try:
        min_lng, min_lat, max_lng, max_lat = (float(x) for x in parts)
    except ValueError:
        return None
    if not (-180.0 <= min_lng <= 180.0 and -180.0 <= max_lng <= 180.0 and -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        return None
    # normalize
    if max_lng < min_lng:
        min_lng, max_lng = max_lng, min_lng
    if max_lat < min_lat:
        min_lat, max_lat = max_lat, min_lat
    return min_lng, min_lat, max_lng, max_lat


def _bbox_poly(min_lng: float, min_lat: float, max_lng: float, max_lat: float) -> Polygon:
    # Polygon.from_bbox: (xmin, ymin, xmax, ymax)
    poly = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    poly.srid = 4326
    return poly


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class _Place:
    type: str
    id: int
    label: str
    lat: float
    lng: float
    hint: str
    url: str


class MapPlacesAPIView(APIView):
    """
    GET /api/map/places/?bbox=minLng,minLat,maxLng,maxLat&types=sto,master,autoshop&brand=<slug|id>&section=<slug>
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "map_places"

    def get(self, request):
        if not getattr(settings, "MAP_FEATURE_ENABLED", False):
            return Response({"detail": "Карта временно недоступна"}, status=503)
        bbox = _parse_bbox(request.query_params.get("bbox"))
        if not bbox:
            return Response({"detail": "bbox обязателен: minLng,minLat,maxLng,maxLat"}, status=400)
        min_lng, min_lat, max_lng, max_lat = bbox
        poly = _bbox_poly(min_lng, min_lat, max_lng, max_lat)

        types_raw = (request.query_params.get("types") or "").strip()
        types = {t.strip() for t in types_raw.split(",") if t.strip()} if types_raw else {"sto", "master", "autoshop"}
        types = types & {"sto", "master", "autoshop"}
        if not types:
            types = {"sto", "master", "autoshop"}

        # Совместимость с фильтрами каталога: exec=sto/private -> types.
        exec_vals = request.query_params.getlist("exec")
        if exec_vals and not types_raw:
            want = set()
            if EXECUTOR_KIND_STO in exec_vals:
                want.add("sto")
            if EXECUTOR_KIND_PRIVATE in exec_vals:
                want.add("master")
            if want:
                types = want

        brand_raw = (request.query_params.get("brand") or "").strip()
        section_slug = (request.query_params.get("section") or "").strip()
        service_slug = (request.query_params.get("service") or "").strip()
        cat_ids = [c for c in request.query_params.getlist("cat") if str(c).strip().isdigit()]

        brand_slug = None
        brand_id = None
        if brand_raw:
            if brand_raw.isdigit():
                brand_id = int(brand_raw)
            else:
                brand_slug = brand_raw

        # service_slug -> category id
        if service_slug:
            from apps.stations.models import ServiceCategory

            found = ServiceCategory.objects.filter(slug=service_slug).values_list("pk", flat=True).first()
            if found is not None:
                sid = str(found)
                if sid not in cat_ids:
                    cat_ids.append(sid)

        today = timezone.localdate()
        out: list[_Place] = []

        if "sto" in types or "master" in types:
            qs = (
                ServiceStation.objects.visible_in_catalog(today=today)
                .exclude(location__isnull=True)
                .filter(location__within=poly)
                .only("pk", "slug", "name", "address", "executor_kind", "parent_station_id", "tagline", "location")
            )
            kind_filter = []
            if "sto" in types:
                kind_filter.append(EXECUTOR_KIND_STO)
            if "master" in types:
                kind_filter.append(EXECUTOR_KIND_PRIVATE)
            if kind_filter:
                qs = qs.filter(executor_kind__in=kind_filter)
            if "master" not in types:
                qs = qs.filter(parent_station__isnull=True)
            if "sto" not in types:
                qs = qs.filter(parent_station__isnull=False)

            if section_slug:
                qs = qs.filter(Q(categories__section__slug=section_slug) | Q(service_sections__slug=section_slug)).distinct()

            if cat_ids:
                qs = qs.filter(categories__id__in=[int(x) for x in cat_ids]).distinct()

            if brand_id is not None or brand_slug is not None:
                cond = Q(car_brands_all=True)
                if brand_id is not None:
                    cond = cond | Q(car_brands__id=brand_id)
                if brand_slug is not None:
                    cond = cond | Q(car_brands__slug=brand_slug)
                qs = qs.filter(cond).distinct()

            for st in qs[:600]:
                loc = st.location
                if not loc:
                    continue
                t = "master" if st.parent_station_id else "sto"
                hint = (st.tagline or st.address or "").strip()
                out.append(
                    _Place(
                        type=t,
                        id=st.pk,
                        label=st.name,
                        lat=round(loc.y, 6),
                        lng=round(loc.x, 6),
                        hint=hint[:140],
                        url=reverse("stations:detail", kwargs={"slug": st.slug}),
                    )
                )

        if "autoshop" in types:
            shops = (
                AutoShopProfile.objects.exclude(location__isnull=True)
                .filter(location__within=poly)
                .only("pk", "slug", "name", "address", "city_label", "description", "location")
            )

            # Фильтр по разделу услуг: магазины показываем в разделе "shop" (если выбран другой раздел — скрываем).
            if section_slug and section_slug != "shop":
                shops = AutoShopProfile.objects.none()

            if (brand_id is not None) or (brand_slug is not None) or cat_ids:
                # Через объявления магазина: part_brand или car_brand
                ad_q = Q(shop_id__isnull=False)
                if cat_ids:
                    # Для магазинов: категории "услуг" не применимы, но если это авто-магазинная категория услуг,
                    # будем считать, что нужно показывать магазины (раздел shop) без доп. ограничения.
                    pass
                if brand_id is not None:
                    ad_q &= Q(part_brand_id=brand_id) | Q(car_brand_id=brand_id)
                else:
                    # slug -> id
                    bid = CarBrand.objects.filter(slug=brand_slug).values_list("pk", flat=True).first()
                    if bid:
                        ad_q &= Q(part_brand_id=bid) | Q(car_brand_id=bid)
                    else:
                        if brand_slug:
                            ad_q &= Q(pk__in=[])
                shop_ids = (
                    Ad.objects.filter(ad_q, is_published=True)
                    .values_list("shop_id", flat=True)
                    .distinct()[:2000]
                )
                shops = shops.filter(pk__in=list(shop_ids))

            for sh in shops[:400]:
                loc = sh.location
                if not loc:
                    continue
                hint = (sh.address or sh.city_label or sh.description or "").strip()
                out.append(
                    _Place(
                        type="autoshop",
                        id=sh.pk,
                        label=sh.name,
                        lat=round(loc.y, 6),
                        lng=round(loc.x, 6),
                        hint=hint[:140],
                        url=reverse("classifieds:shop_detail", kwargs={"slug": sh.slug}),
                    )
                )

        return Response({"count": len(out), "results": [p.__dict__ for p in out]})

