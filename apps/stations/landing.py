"""Публичные SEO-лендинги: категория услуги, марка авто, раздел услуг."""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse
from django.views.generic import DetailView
from django.utils import timezone

from apps.core.visitor_city import SESSION_KEY as VISITOR_CITY_SESSION_KEY
from django.utils.safestring import mark_safe

from apps.core.seo import clamp_seo_description

from .catalog_city import filter_queryset_by_visitor_city
from .landing_seo import (
    build_service_category_seo,
    normalized_landing_faq,
    service_category_faq_json_ld,
)
from .models import CarBrand, ServiceCategory, ServiceSection, ServiceStation
from .section_seo import build_service_section_seo, service_section_faq_json_ld
from .breadcrumb_schema import breadcrumb_json_ld


def _visible_stations_qs(today, *, city_label: str | None):
    qs = ServiceStation.objects.visible_in_catalog(today=today).filter(is_active=True)
    if city_label:
        qs = filter_queryset_by_visitor_city(qs, city_label)
    return qs


def catalog_href_service(category_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?service={quote(category_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


def catalog_href_service_brand(category_slug: str, brand_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?service={quote(category_slug)}&brand={quote(brand_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


def catalog_href_brand(brand_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?brand={quote(brand_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


def catalog_href_brand_section(brand_slug: str, section_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?brand={quote(brand_slug)}&section={quote(section_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


def catalog_href_section(section_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?section={quote(section_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


def catalog_href_section_brand(section_slug: str, brand_slug: str, *, city: str | None) -> str:
    from django.urls import reverse

    base = f"{reverse('stations:list')}?section={quote(section_slug)}&brand={quote(brand_slug)}"
    if city:
        return f"{base}&city={quote(city)}"
    return base


class ServiceCategoryLandingView(DetailView):
    model = ServiceCategory
    slug_url_kwarg = "slug"
    context_object_name = "category"
    template_name = "stations/service_category_landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        cat = self.object
        city = (self.request.GET.get("city") or "").strip() or (
            self.request.session.get(VISITOR_CITY_SESSION_KEY) or ""
        ).strip() or None
        visible = _visible_stations_qs(today, city_label=city)
        providers_qs = visible.filter(categories=cat)
        ctx["provider_count"] = providers_qs.distinct().count()
        ctx["catalog_href"] = catalog_href_service(cat.slug, city=city)

        # Марки авто для этой услуги: если есть исполнители "все марки" — показываем популярные,
        # иначе — марки, которые реально привязаны к исполнителям с данной категорией.
        brands: list[CarBrand] = []
        brand_ids = list(providers_qs.values_list("car_brands__pk", flat=True).distinct())
        if brand_ids:
            brands = list(
                CarBrand.objects.filter(pk__in=brand_ids).order_by("-is_popular", "sort_order", "name")[:18]
            )

        has_all_brands = providers_qs.filter(car_brands_all=True).exists() if providers_qs.exists() else False
        if has_all_brands or not brands:
            popular = list(CarBrand.objects.filter(is_popular=True).order_by("sort_order", "name")[:18])
            existing = {b.pk for b in brands}
            for b in popular:
                if b.pk in existing:
                    continue
                brands.append(b)
                existing.add(b.pk)
                if len(brands) >= 18:
                    break
        ctx["top_brand_links"] = [
            {
                "slug": b.slug,
                "name": b.name,
                "stem": b.logo_png_stem,
                "href": catalog_href_service_brand(cat.slug, b.slug, city=city),
            }
            for b in brands
        ]

        related = (
            ServiceCategory.objects.filter(stations__in=visible)
            .exclude(pk=cat.pk)
            .annotate(n=Count("stations", distinct=True))
            .filter(n__gt=0)
            .order_by("-n", "name")[:16]
        )
        ctx["related_categories"] = related

        focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
        geo = city or focus or None
        title, desc = build_service_category_seo(cat, geo=city)
        ctx["seo_og_title"] = title
        ctx["seo_meta_description"] = desc

        ctx["landing_lead"] = (cat.landing_lead or "").strip()
        faq_items = normalized_landing_faq(cat.landing_faq)
        ctx["landing_faq"] = faq_items
        ctx["faq_json_ld"] = mark_safe(service_category_faq_json_ld(request=self.request, category=cat, faq_items=faq_items))
        ctx["breadcrumb_json_ld"] = mark_safe(
            breadcrumb_json_ld(
                request=self.request,
                items=[
                    ("Главная", reverse("home")),
                    ("Каталог", reverse("stations:list")),
                    (cat.name, reverse("landing:service_category", kwargs={"slug": cat.slug})),
                ],
            )
        )
        return ctx


class ServiceSectionLandingView(DetailView):
    model = ServiceSection
    slug_url_kwarg = "slug"
    context_object_name = "section"
    template_name = "stations/service_section_landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        sec = self.object
        city = (self.request.GET.get("city") or "").strip() or (
            self.request.session.get(VISITOR_CITY_SESSION_KEY) or ""
        ).strip() or None
        visible = _visible_stations_qs(today, city_label=city)

        providers_qs = visible.filter(Q(categories__section=sec) | Q(service_sections=sec)).distinct()
        ctx["provider_count"] = providers_qs.count()
        ctx["catalog_href"] = catalog_href_section(sec.slug, city=city)

        pre_brand = (self.request.GET.get("brand") or "").strip()
        ctx["selected_brand_slug"] = pre_brand

        # Марки строго по реальным исполнителям этого раздела (+ all brands как fallback к популярным)
        brands: list[CarBrand] = []
        brand_ids = list(providers_qs.values_list("car_brands__pk", flat=True).distinct())
        if brand_ids:
            brands = list(
                CarBrand.objects.filter(pk__in=brand_ids).order_by("-is_popular", "sort_order", "name")[:18]
            )
        has_all_brands = providers_qs.filter(car_brands_all=True).exists() if providers_qs.exists() else False
        if has_all_brands:
            popular = list(CarBrand.objects.filter(is_popular=True).order_by("sort_order", "name")[:18])
            existing = {b.pk for b in brands}
            for b in popular:
                if b.pk in existing:
                    continue
                brands.append(b)
                existing.add(b.pk)
                if len(brands) >= 18:
                    break

        if pre_brand:
            # Если марка передана из лендинга марки — усиливаем CTA "сразу в каталог"
            if any(b.slug == pre_brand for b in brands) or has_all_brands:
                ctx["catalog_href_brand"] = catalog_href_section_brand(sec.slug, pre_brand, city=city)
            else:
                ctx["catalog_href_brand"] = ""
        else:
            ctx["catalog_href_brand"] = ""

        ctx["top_brand_links"] = [
            {
                "slug": b.slug,
                "name": b.name,
                "stem": b.logo_png_stem,
                "href": catalog_href_section_brand(sec.slug, b.slug, city=city),
            }
            for b in brands
        ]

        focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
        geo = city or focus or None
        title, desc = build_service_section_seo(sec, geo=city)
        ctx["seo_og_title"] = title
        ctx["seo_meta_description"] = desc

        ctx["landing_lead"] = (sec.landing_lead or "").strip()
        faq_items = normalized_landing_faq(sec.landing_faq)
        ctx["landing_faq"] = faq_items
        ctx["faq_json_ld"] = mark_safe(
            service_section_faq_json_ld(request=self.request, section=sec, faq_items=faq_items)
        )
        ctx["breadcrumb_json_ld"] = mark_safe(
            breadcrumb_json_ld(
                request=self.request,
                items=[
                    ("Главная", reverse("home")),
                    ("Каталог", reverse("stations:list")),
                    (sec.name, reverse("landing:service_section", kwargs={"slug": sec.slug})),
                ],
            )
        )
        return ctx


class CarBrandLandingView(DetailView):
    model = CarBrand
    slug_url_kwarg = "slug"
    context_object_name = "brand"
    template_name = "stations/car_brand_landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        brand = self.object
        city = (self.request.GET.get("city") or "").strip() or (
            self.request.session.get(VISITOR_CITY_SESSION_KEY) or ""
        ).strip() or None
        visible = _visible_stations_qs(today, city_label=city)
        providers_qs = visible.filter(Q(car_brands=brand) | Q(car_brands_all=True))
        ctx["provider_count"] = providers_qs.distinct().count()
        ctx["catalog_href"] = catalog_href_brand(brand.slug, city=city)

        # Разделы по марке: показываем то, что реально есть у исполнителей (через categories.section и быстрый выбор service_sections).
        sections = (
            ServiceSection.objects.filter(
                Q(categories__stations__in=providers_qs) | Q(stations__in=providers_qs)
            )
            .distinct()
            .order_by("sort_order", "name")
        )
        ctx["top_sections"] = [
            {
                "slug": s.slug,
                "name": s.name,
                "icon": (s.icon or "").strip() or "bi-tools",
                "label": s.name,
                "href": catalog_href_brand_section(brand.slug, s.slug, city=city),
            }
            for s in sections
        ]

        focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
        geo = city or focus
        if geo:
            ctx["seo_og_title"] = f"Ремонт и обслуживание {brand.name} в {geo} | МаБибип"
            ctx["seo_meta_description"] = clamp_seo_description(
                f"{brand.name} в {geo}: СТО и мастера, топ услуг по марке, отзывы и онлайн-запись — МаБибип."
            )
        else:
            ctx["seo_og_title"] = f"Ремонт и обслуживание {brand.name} | МаБибип"
            ctx["seo_meta_description"] = clamp_seo_description(
                f"{brand.name}: каталог исполнителей, популярные услуги, запись онлайн — МаБибип."
            )
        ctx["breadcrumb_json_ld"] = mark_safe(
            breadcrumb_json_ld(
                request=self.request,
                items=[
                    ("Главная", reverse("home")),
                    ("Каталог", reverse("stations:list")),
                    (brand.name, reverse("landing:car_brand", kwargs={"slug": brand.slug})),
                ],
            )
        )
        return ctx
