"""Sitemap для публичных страниц (фаза A: индексация без параметров мусора)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.classifieds.models import Ad, AutoShopProfile
from apps.stations.models import CarBrand, ServiceCategory, ServiceSection, ServiceStation


class SiteBaseURLMixin:
    """
    Полные URL в sitemap строятся по SITE_BASE_URL (схема + host), если задан;
    иначе — стандартно из django.contrib.sites.
    """

    def get_urls(self, page: int = 1, site: Any = None, protocol: str | None = None) -> list:
        base = (getattr(settings, "SITE_BASE_URL", None) or "").strip()
        if base:
            parsed = urlparse(base)
            if parsed.netloc:

                class _Site:
                    domain = parsed.netloc

                site = _Site()
                protocol = parsed.scheme or (protocol or "https")
        return super().get_urls(page=page, site=site, protocol=protocol)


class StaticViewSitemap(SiteBaseURLMixin, Sitemap):
    """Главная, каталог без фильтров, карта «Рядом»."""

    changefreq = "daily"

    def items(self) -> list[str]:
        items = ["home", "stations:list", "classifieds:ads_list"]
        if getattr(settings, "MAP_FEATURE_ENABLED", False):
            items.insert(2, "stations:nearby_map")
        return items

    def location(self, item: str) -> str:
        if item == "home":
            return "/"
        if item == "stations:list":
            return reverse("stations:list")
        if item == "classifieds:ads_list":
            return reverse("classifieds:ads_list")
        return reverse("stations:nearby_map")

    def priority(self, item: str) -> float:  # type: ignore[override]
        if item == "home":
            return 1.0
        if item == "classifieds:ads_list":
            return 0.85
        return 0.8


class ServiceCategorySitemap(SiteBaseURLMixin, Sitemap):
    """Лендинги услуг /uslugi/<slug>/ — только категории с исполнителями в каталоге."""

    changefreq = "weekly"
    priority = 0.75

    def items(self):
        today = timezone.localdate()
        vis = (
            ServiceStation.objects.visible_in_catalog(today=today)
            .filter(is_active=True)
        )
        return list(
            ServiceCategory.objects.filter(stations__in=vis).distinct().order_by("pk"),
        )

    def location(self, obj: ServiceCategory) -> str:
        return reverse("landing:service_category", kwargs={"slug": obj.slug})


class CarBrandSitemap(SiteBaseURLMixin, Sitemap):
    """Лендинги марок /marki/<slug>/ — марки, по которым есть СТО в каталоге."""

    changefreq = "weekly"
    priority = 0.72

    def items(self):
        today = timezone.localdate()
        vis = (
            ServiceStation.objects.visible_in_catalog(today=today)
            .filter(is_active=True)
        )
        return list(CarBrand.objects.filter(stations__in=vis).distinct().order_by("pk"))

    def location(self, obj: CarBrand) -> str:
        return reverse("landing:car_brand", kwargs={"slug": obj.slug})


class ServiceSectionSitemap(SiteBaseURLMixin, Sitemap):
    """Лендинги разделов /razdely/<slug>/ — только разделы с исполнителями в каталоге."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        today = timezone.localdate()
        vis = ServiceStation.objects.visible_in_catalog(today=today).filter(is_active=True)
        return list(
            ServiceSection.objects.filter(Q(categories__stations__in=vis) | Q(stations__in=vis))
            .distinct()
            .order_by("pk")
        )

    def location(self, obj: ServiceSection) -> str:
        return reverse("landing:service_section", kwargs={"slug": obj.slug})


class StationSitemap(SiteBaseURLMixin, Sitemap):
    """Карточки СТО/мастеров, видимых в каталоге на сегодня."""

    changefreq = "weekly"
    priority = 0.6

    def items(self):
        today = timezone.localdate()
        return (
            ServiceStation.objects.visible_in_catalog(today=today)
            .filter(is_active=True)
            .order_by("pk")
        )

    def location(self, obj: ServiceStation) -> str:
        return reverse("stations:detail", kwargs={"slug": obj.slug})


class ClassifiedAdsSitemap(SiteBaseURLMixin, Sitemap):
    """Публичные объявления /ads/<id>/ — только опубликованные."""

    changefreq = "daily"
    priority = 0.55

    def items(self):
        return Ad.objects.filter(is_published=True).order_by("pk")

    def location(self, obj: Ad) -> str:
        return reverse("classifieds:ad_detail", kwargs={"pk": obj.pk})


class AutoShopSitemap(SiteBaseURLMixin, Sitemap):
    """Профили автомагазинов /shops/<slug>/."""

    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return AutoShopProfile.objects.order_by("pk")

    def location(self, obj: AutoShopProfile) -> str:
        return reverse("classifieds:shop_detail", kwargs={"slug": obj.slug})
