"""Публичное API каталога (DRF)."""

from __future__ import annotations

import hashlib

from django.core.cache import cache
from django.db.models import Avg, Q
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.bookings.constants import BookingStatus
from apps.stations.models import ServiceStation
from apps.stations.nearby import list_nearby_stations
from apps.stations.smart_search import build_search_suggestions


def _round_coord(v: float, decimals: int = 4) -> float:
    return round(v, decimals)


class NearbyStationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.SlugField()
    name = serializers.CharField()
    address = serializers.CharField()
    distance_km = serializers.FloatField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    avg_rating = serializers.FloatField(allow_null=True)


class NearbyPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 50


class StationsNearbyAPIView(APIView):
    """
    GET /api/stations/nearby/?lat=&lng=&radius_km=5
    Только СТО с заполненной точкой на карте и видимые в каталоге.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat", ""))
            lng = float(request.query_params.get("lng", ""))
        except (TypeError, ValueError):
            return Response({"detail": "Параметры lat и lng обязательны и должны быть числами."}, status=400)

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return Response({"detail": "lat должен быть в [-90, 90], lng в [-180, 180]."}, status=400)

        try:
            radius_km = float(request.query_params.get("radius_km", "5"))
        except (TypeError, ValueError):
            return Response({"detail": "radius_km должен быть числом."}, status=400)
        if not (0 < radius_km <= 100):
            return Response({"detail": "radius_km должен быть в (0, 100]."}, status=400)

        paginator = NearbyPagination()
        limit = paginator.get_limit(request) or NearbyPagination.default_limit
        offset = paginator.get_offset(request)

        page_rows, total = list_nearby_stations(lat=lat, lng=lng, radius_km=radius_km, limit=limit, offset=offset)

        ids = [st.pk for st, _ in page_rows]
        ratings = {}
        if ids:
            agg = (
                ServiceStation.objects.filter(pk__in=ids)
                .annotate(
                    avg_rating=Avg(
                        "reviews__rating",
                        filter=Q(
                            reviews__moderation_status__in=["ok", "under_review"],
                        ),
                    )
                )
                .values("id", "avg_rating")
            )
            ratings = {row["id"]: row["avg_rating"] for row in agg}

        data = []
        for st, dkm in page_rows:
            data.append(
                {
                    "id": st.pk,
                    "slug": st.slug,
                    "name": st.name,
                    "address": st.address,
                    "distance_km": dkm,
                    "lat": _round_coord(st.location.y),
                    "lng": _round_coord(st.location.x),
                    "avg_rating": float(ratings.get(st.pk)) if ratings.get(st.pk) is not None else None,
                }
            )

        return Response(
            {
                "count": total,
                "results": NearbyStationSerializer(data, many=True).data,
            }
        )


class SearchSuggestAPIView(APIView):
    """
    GET /api/search/suggest/?q=
    Подсказки: словарь «живых» фраз, категории услуг, СТО из видимого каталога.
    Доп. поля: services, stations, ambiguous_hint; кэш 1 ч при настроенном Redis.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "search_suggest"

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 1:
            return Response(
                {
                    "results": [],
                    "services": [],
                    "sections": [],
                    "masters": [],
                    "stations": [],
                    "ambiguous_hint": None,
                }
            )

        try:
            limit_services = int(request.query_params.get("limit_services", "8"))
        except (TypeError, ValueError):
            limit_services = 8
        try:
            limit_sections = int(request.query_params.get("limit_sections", "6"))
        except (TypeError, ValueError):
            limit_sections = 6
        try:
            limit_masters = int(request.query_params.get("limit_masters", "4"))
        except (TypeError, ValueError):
            limit_masters = 4
        try:
            limit_stations = int(request.query_params.get("limit_stations", "3"))
        except (TypeError, ValueError):
            limit_stations = 3
        limit_services = max(1, min(limit_services, 20))
        limit_sections = max(0, min(limit_sections, 20))
        limit_masters = max(0, min(limit_masters, 20))
        limit_stations = max(0, min(limit_stations, 10))
        services_only = request.query_params.get("services_only", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )

        today = timezone.localdate()
        visible = ServiceStation.objects.visible_in_catalog(today=today)

        cache_key = (
            "search_suggest:v4:"
            + hashlib.sha256(
                f"{q}|{limit_services}|{limit_sections}|{limit_masters}|{limit_stations}|{services_only}|{today.isoformat()}".encode()
            ).hexdigest()[:40]
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        payload = build_search_suggestions(
            q_raw=q,
            visible_stations=visible,
            service_limit=limit_services,
            section_limit=limit_sections,
            master_limit=limit_masters,
            station_limit=limit_stations if not services_only else 0,
            include_stations=not services_only,
            include_masters=not services_only,
        )
        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)
