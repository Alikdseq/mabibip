import json
import logging
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, ListView, TemplateView

from apps.bookings.constants import BookingStatus
from apps.bookings.exceptions import BookingSlotConflictError, SlotNotBookableError
from apps.bookings.forms import BookingRequestForm
from apps.bookings.models import TimeSlot
from apps.bookings.redis_holds import acquire_or_refresh_slot_hold
from apps.bookings.services import create_booking_request
from apps.bookings.slot_rules import slot_is_bookable
from apps.core.decorators import htmx_login_required
from apps.core.seo import clamp_seo_description
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review
from apps.reviews.services import (
    ReviewAlreadyExistsError,
    create_station_review,
    user_has_station_review,
)
from apps.users.models import FavoriteStation, SavedCar
from apps.stations.card_cache import get_station_card_cache, set_station_card_cache
from apps.stations.constants import (
    ADDRESS_PUBLIC_AFTER_BOOKING,
    CATALOG_DAY_RANGE,
    EXECUTOR_KIND_PRIVATE,
    EXECUTOR_KIND_STO,
)
from apps.stations.detail_schema import station_detail_json_ld, station_primary_image_url
from apps.stations.display import (
    format_public_address,
    map_links_wgs84,
    mask_phone_e164,
    review_author_public_name,
    station_contact_phone_e164,
    telegram_href,
)

from apps.core.visitor_city import SESSION_KEY as VISITOR_CITY_SESSION_KEY

from .catalog_query import build_catalog_queryset
from .catalog_seo import build_catalog_page_seo
from .homepage import all_service_section_tiles, build_homepage_context
from .models import CarBrand, District, ServiceCategory, ServiceSection, ServiceStation, StationPhoto, StationServiceOffer
from .nearby import list_nearby_stations
from .selectors import (
    annotate_has_slots_today,
    annotate_has_slots_tomorrow,
    annotate_nearest_free_slot,
    annotate_station_ratings,
    station_has_slots_today,
)
from .visibility import station_accepts_online_booking, station_is_visible

logger = logging.getLogger(__name__)


def _saved_cars_for_booking_form(user):
    if not getattr(user, "is_authenticated", False):
        return []
    return list(SavedCar.objects.filter(user=user).order_by("-updated_at")[:20])


def _visible_station_queryset():
    return ServiceStation.objects.visible_in_catalog(today=timezone.localdate())


class NearbyStationsMapView(TemplateView):
    """
    Интерактивная карта СТО в радиусе от точки пользователя.
    GET: lat, lng (WGS84), radius_km (по умолчанию 10, макс. 50).
    """

    template_name = "stations/nearby_map.html"

    def get_template_names(self):
        if not getattr(settings, "MAP_FEATURE_ENABLED", False):
            return ["stations/map_disabled.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        if not getattr(settings, "MAP_FEATURE_ENABLED", False):
            ctx = super().get_context_data(**kwargs)
            ctx["page_title"] = "Карта"
            return ctx
        ctx = super().get_context_data(**kwargs)
        req = self.request.GET
        lat_raw = (req.get("lat") or "").strip()
        lng_raw = (req.get("lng") or "").strip()
        radius_raw = (req.get("radius_km") or "10").strip()
        lat_f = lng_f = None
        if lat_raw and lng_raw:
            try:
                lat_f = float(lat_raw)
                lng_f = float(lng_raw)
            except ValueError:
                pass
            if lat_f is not None and not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
                lat_f = lng_f = None
        try:
            r_km = float(radius_raw)
        except ValueError:
            r_km = 10.0
        r_km = max(0.5, min(r_km, 50.0))

        points: list[dict] = []
        if lat_f is not None:
            rows, _total = list_nearby_stations(
                lat=lat_f,
                lng=lng_f,
                radius_km=r_km,
                limit=100,
                offset=0,
            )
            for st, dkm in rows:
                if st.location:
                    points.append(
                        {
                            "lat": round(st.location.y, 5),
                            "lon": round(st.location.x, 5),
                            "name": st.name,
                            "slug": st.slug,
                            "address": (st.address or "")[:220],
                            "distance_km": round(dkm, 1),
                            "url": reverse("stations:detail", kwargs={"slug": st.slug}),
                        }
                    )

        catalog_qs = {}
        if lat_f is not None:
            catalog_qs = {
                "user_lat": str(lat_f),
                "user_lng": str(lng_f),
                "radius_km": str(int(r_km)) if r_km == int(r_km) else str(r_km),
                "sort": "distance",
            }
        ctx.update(
            {
                "map_points": points,
                "map_points_json": json.dumps(points, ensure_ascii=False),
                "user_lat": lat_f,
                "user_lng": lng_f,
                "user_lat_json": json.dumps(lat_f) if lat_f is not None else "null",
                "user_lng_json": json.dumps(lng_f) if lng_f is not None else "null",
                "radius_km": r_km,
                "station_count": len(points),
                "catalog_nearby_url": f"{reverse('stations:list')}?{urlencode(catalog_qs)}"
                if catalog_qs
                else reverse("stations:list"),
                "map_places_api_url": reverse("api_map_places"),
                "car_brand_choices": list(CarBrand.objects.order_by("-is_popular", "sort_order", "name").values("id", "name", "slug")),
                "service_section_choices": list(ServiceSection.objects.order_by("sort_order", "name").values("id", "name", "slug")),
            }
        )
        return ctx


def _active_station_queryset():
    """Публичная карточка: активные СТО (в т.ч. не в каталоге из‑за подписки)."""
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    qs = ServiceStation.objects.filter(is_active=True).select_related("owner", "district")
    qs = annotate_station_ratings(qs)
    qs = annotate_has_slots_today(qs, today)
    qs = annotate_has_slots_tomorrow(qs, tomorrow)
    qs = annotate_nearest_free_slot(qs, today)
    return qs.prefetch_related(
        "categories",
        "car_brands",
        Prefetch("photos", queryset=StationPhoto.objects.order_by("order", "pk")),
        Prefetch(
            "service_offers",
            queryset=StationServiceOffer.objects.select_related("category").order_by(
                "category__name",
                "pk",
            ),
        ),
        "bays",
    )


def _bookable_slots(station_id: int, day: date, *, for_user=None):
    now = timezone.now()
    qs = (
        TimeSlot.objects.filter(
            bay__station_id=station_id,
            date=day,
            is_available=True,
        )
        .select_related("bay")
        .order_by("start_time", "pk")
    )
    return [s for s in qs if slot_is_bookable(s, now=now, for_user=for_user)]


def _clamp_booking_calendar_day(raw: str | None) -> date:
    """Дата из querystring ограничена сеткой каталога: сегодня … сегодня+(CATALOG_DAY_RANGE-1)."""
    today = timezone.localdate()
    last = today + timedelta(days=CATALOG_DAY_RANGE - 1)
    if not raw:
        return today
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return today
    if d < today:
        return today
    if d > last:
        return last
    return d


class StationListView(ListView):
    model = ServiceStation
    context_object_name = "stations"
    template_name = "stations/station_list.html"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        from apps.stations.catalog_redirect import redirect_if_service_only_catalog

        redir = redirect_if_service_only_catalog(request)
        if redir:
            return redir
        if not getattr(settings, "MAP_FEATURE_ENABLED", False) and (request.GET.get("view") or "").strip().lower() == "map":
            qd = request.GET.copy()
            qd.pop("view", None)
            target = request.path + (f"?{qd.urlencode()}" if qd else "")
            return redirect(target)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs, meta = build_catalog_queryset(
            self.request.GET,
            visitor_city_label=self.request.session.get(VISITOR_CITY_SESSION_KEY),
        )
        self._catalog_meta = meta
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self._catalog_meta)
        cat_ids = self._catalog_meta.get("catalog_cat_ids") or []
        ctx["catalog_selected_categories"] = list(
            ServiceCategory.objects.filter(pk__in=cat_ids).order_by("name")
        )
        ctx["categories"] = ServiceCategory.objects.all().order_by("name")
        ctx["districts"] = District.objects.all().order_by("city_label", "name")
        popular = list(CarBrand.objects.filter(is_popular=True).order_by("sort_order", "name"))
        ctx["car_brands_primary"] = popular[:9]
        ctx["car_brands_10th"] = popular[9] if len(popular) > 9 else None
        ctx["car_brands_more"] = popular[10:] + list(
            CarBrand.objects.filter(is_popular=False).order_by("sort_order", "name")
        )
        ctx["catalog_listing"] = True
        ctx["catalog_view"] = (self.request.GET.get("view") or "list").strip().lower()
        if ctx["catalog_view"] not in ("list", "map"):
            ctx["catalog_view"] = "list"
        if not getattr(settings, "MAP_FEATURE_ENABLED", False):
            ctx["catalog_view"] = "list"
        qd = self.request.GET.copy()
        if "view" in qd:
            qd.pop("view")
        ctx["catalog_qs_no_view"] = urlencode(qd, doseq=True)
        ctx["catalog_map_filters"] = {
            "brand": (ctx.get("catalog_brand") or "").strip(),
            "section": (ctx.get("catalog_section") or "").strip(),
            "service": (ctx.get("catalog_service_slug") or "").strip(),
            "cat": ctx.get("catalog_cat_ids") or [],
            "exec": ctx.get("catalog_exec") or [],
        }
        v_city = (self.request.session.get(VISITOR_CITY_SESSION_KEY) or "").strip() or None
        ctx["catalog_section_tiles"] = all_service_section_tiles(
            timezone.localdate(),
            city_label=v_city,
        )
        ctx["executor_sto"] = EXECUTOR_KIND_STO
        ctx["executor_private"] = EXECUTOR_KIND_PRIVATE
        ctx["map_places_api_url"] = reverse("api_map_places")
        ctx["search_q"] = self._catalog_meta["catalog_q"]
        ctx["slots_today"] = "1" if self._catalog_meta["catalog_slots_today"] else ""
        ctx["rating_gt"] = ""
        seo = build_catalog_page_seo(
            meta=self._catalog_meta,
            visitor_city_label=v_city,
            category_names=[c.name for c in ctx["catalog_selected_categories"]],
        )
        ctx.update(seo)
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request") == "true":
            return render(self.request, "stations/partials/catalog_results.html", context)
        return super().render_to_response(context, **response_kwargs)


class StationDetailView(DetailView):
    model = ServiceStation
    template_name = "stations/station_detail.html"
    context_object_name = "station"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return _active_station_queryset().select_related("parent_station")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        station = self.object
        today = timezone.localdate()
        if get_station_card_cache(station.pk) is None:
            set_station_card_cache(
                station.pk,
                {
                    "name": station.name,
                    "slug": station.slug,
                    "avg_rating": (
                        float(station.avg_rating) if station.avg_rating is not None else None
                    ),
                },
            )
        ctx["today"] = today
        ctx["tomorrow"] = today + timedelta(days=1)
        ctx["has_slots_today"] = station_has_slots_today(station.pk, today)
        ctx["can_book_online"] = station_accepts_online_booking(station, today)
        ctx["visible_in_catalog"] = station_is_visible(station, today)
        ctx["booking_week"] = [today + timedelta(days=i) for i in range(CATALOG_DAY_RANGE)]
        ctx["public_address"] = format_public_address(station)
        phone_e164 = station_contact_phone_e164(station)
        ctx["contact_phone_e164"] = phone_e164
        ctx["contact_phone_masked"] = mask_phone_e164(phone_e164)
        u = self.request.user
        ctx["show_full_phone"] = u.is_authenticated
        ctx["whatsapp_url"] = ""
        ctx["telegram_url"] = telegram_href(station.telegram_username) if u.is_authenticated else ""
        ctx["map_yandex_url"], ctx["map_google_url"] = map_links_wgs84(station.location)
        ctx["show_map_links"] = station.location is not None and (
            station.address_public_mode != ADDRESS_PUBLIC_AFTER_BOOKING
        )
        photos = list(station.photos.all())
        ctx["profile_photos"] = [p for p in photos if not p.is_work_sample]
        ctx["work_photos"] = [p for p in photos if p.is_work_sample]
        ctx["executor_sto"] = EXECUTOR_KIND_STO
        ctx["executor_private"] = EXECUTOR_KIND_PRIVATE
        ctx["show_legal_block"] = u.is_authenticated and not getattr(u, "is_sto_owner", False)
        ctx["station_is_favorite"] = (
            u.is_authenticated
            and FavoriteStation.objects.filter(user=u, station=station).exists()
        )

        if station.executor_kind == EXECUTOR_KIND_STO:
            ctx["service_masters"] = list(
                ServiceStation.objects.visible_in_catalog(today=today)
                .filter(parent_station=station)
                .select_related("parent_station")
                .order_by("name", "pk")
            )
        else:
            ctx["service_masters"] = []

        offers = list(station.service_offers.all())
        ctx["has_price_list"] = bool(offers)
        ctx["price_preview"] = offers[:6]
        ctx["price_offer_count"] = len(offers)

        addr_snip = (ctx["public_address"] or "")[:100]
        rev_n = int(getattr(station, "review_count", 0) or 0)
        if station.avg_rating is not None:
            rev_bit = f" ({rev_n} отзывов)" if rev_n else ""
            ctx["meta_description"] = (
                f"{station.name} — {addr_snip}. Рейтинг {float(station.avg_rating):.1f}{rev_bit}. "
                "Запись онлайн — МаБибип."
            )
        else:
            ctx["meta_description"] = (
                f"{station.name} — {addr_snip}. Услуги и запись онлайн — МаБибип."
            )
        ctx["meta_description"] = ctx["meta_description"][:320]
        ctx["seo_meta_description"] = ctx["meta_description"]
        ctx["seo_og_title"] = f"{station.name} — запись онлайн, отзывы, цены — МаБибип"
        if len(ctx["seo_og_title"]) > 68:
            ctx["seo_og_title"] = f"{station.name} — МаБибип"
        ctx["seo_og_image"] = station_primary_image_url(station, request=self.request) or ""

        ctx["schema_json_ld"] = mark_safe(station_detail_json_ld(station, request=self.request))

        all_reviews = list(
            Review.objects.filter(
                station=station,
                moderation_status__in=["ok", "under_review"],
            )
            .select_related("author", "booking", "booking__client", "owner_reply")
            .order_by("-created_at"),
        )
        cutoff = timezone.now() - timedelta(days=183)
        ctx["recent_reviews"] = [r for r in all_reviews if r.created_at >= cutoff]
        ctx["archived_reviews"] = [r for r in all_reviews if r.created_at < cutoff]
        ctx["reviews_preview"] = ctx["recent_reviews"][:5]
        ctx["reviews_more_count"] = max(0, len(ctx["recent_reviews"]) - 5)
        rc = Counter(r.rating for r in ctx["recent_reviews"])
        n = len(ctx["recent_reviews"]) or 1
        ctx["review_star_bars"] = [
            {"stars": s, "count": rc.get(s, 0), "pct": round(100 * rc.get(s, 0) / n, 1)}
            for s in (5, 4, 3, 2, 1)
        ]
        ctx["review_names"] = {
            r.pk: review_author_public_name(r) for r in ctx["recent_reviews"]
        }
        ctx["can_leave_station_review"] = (
            u.is_authenticated
            and u.pk != station.owner_id
            and not user_has_station_review(author=u, station=station)
        )
        return ctx


def _station_review_redirect(request, station: ServiceStation):
    next_raw = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_raw.startswith("/"):
        return redirect(next_raw)
    return redirect(reverse("stations:detail", kwargs={"slug": station.slug}) + "#reviews")


@login_required
@require_http_methods(["GET", "POST"])
def station_review_create(request, slug):
    station = get_object_or_404(_active_station_queryset(), slug=slug)
    if request.user.pk == station.owner_id:
        messages.error(request, "Нельзя оставить отзыв своей станции.")
        return redirect(reverse("stations:detail", kwargs={"slug": station.slug}))
    if user_has_station_review(author=request.user, station=station):
        messages.info(request, "Вы уже оставили отзыв об этом сервисе.")
        return _station_review_redirect(request, station)

    next_raw = (request.POST.get("next") or request.GET.get("next") or "").strip()

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                review = create_station_review(
                    author=request.user,
                    station=station,
                    rating=form.cleaned_data["rating"],
                    text=form.cleaned_data.get("text") or "",
                    photo=form.cleaned_data.get("photo"),
                )
            except ReviewAlreadyExistsError:
                messages.warning(
                    request,
                    "Отзыв уже был сохранён. Если страница открыта в нескольких вкладках, обновите её.",
                )
                return _station_review_redirect(request, station)

            rid = review.pk

            def _notify_sto() -> None:
                from apps.reviews.mail import mail_sto_new_review

                try:
                    rev = Review.objects.select_related("station", "station__owner").get(pk=rid)
                    mail_sto_new_review(rev)
                except Exception:
                    logger.exception("mail_sto_new_review failed review_id=%s", rid)

            transaction.on_commit(_notify_sto)
            messages.success(request, "Спасибо, ваш отзыв сохранён.")
            return _station_review_redirect(request, station)
    else:
        form = ReviewForm()

    return render(
        request,
        "stations/station_review_form.html",
        {
            "station": station,
            "form": form,
            "review_next_url": next_raw,
        },
    )


def station_slots_partial(request, slug):
    station = get_object_or_404(_active_station_queryset(), slug=slug)
    today = timezone.localdate()
    if not station_accepts_online_booking(station, today):
        return render(
            request,
            "stations/partials/booking_subscription_paused.html",
            {"station": station},
        )
    day = _clamp_booking_calendar_day(request.GET.get("date"))
    # Автозаполняем слоты для записи, чтобы пользователи всегда видели окна 10:00–18:00 (шаг 1 час),
    # а владелец мог вручную закрывать лишние слоты в календаре.
    try:
        from apps.bookings.slot_generation import run_generate_slots_for_station

        # Генерируем только короткий горизонт, чтобы не нагружать страницу
        run_generate_slots_for_station(station_id=station.pk, today=today, days_ahead=14)
    except Exception:
        # best-effort: слоты могли быть созданы заранее; даже при ошибке показываем то, что есть.
        pass
    user = request.user if request.user.is_authenticated else None
    slots = _bookable_slots(station.pk, day, for_user=user)
    modal_body = (request.GET.get("modal_body") or "bookingModalBody").strip()
    if not modal_body.replace("_", "").isalnum():
        modal_body = "bookingModalBody"
    return render(
        request,
        "stations/partials/slots_day.html",
        {
            "station": station,
            "slots": slots,
            "day": day,
            "booking_modal_body_id": modal_body,
        },
    )


@htmx_login_required
@require_http_methods(["GET"])
def booking_form_partial(request, slug, slot_id):
    station = get_object_or_404(_active_station_queryset(), slug=slug)
    today = timezone.localdate()
    if not station_accepts_online_booking(station, today):
        return render(
            request,
            "stations/partials/booking_subscription_paused.html",
            {"station": station},
            status=403,
        )
    slot = get_object_or_404(TimeSlot, pk=slot_id, bay__station=station)
    if not acquire_or_refresh_slot_hold(slot.pk, request.user.pk):
        return render(
            request,
            "stations/partials/booking_unavailable.html",
            {"station": station},
        )
    if not slot_is_bookable(slot, for_user=request.user):
        return render(
            request,
            "stations/partials/booking_unavailable.html",
            {"station": station},
        )
    form = BookingRequestForm(slot=slot, booking_user=request.user)
    modal_body = (request.GET.get("modal_body") or "bookingModalBody").strip()
    if not modal_body.replace("_", "").isalnum():
        modal_body = "bookingModalBody"
    return render(
        request,
        "stations/partials/booking_form.html",
        {
            "form": form,
            "station": station,
            "slot": slot,
            "booking_modal_body_id": modal_body,
            "saved_cars": _saved_cars_for_booking_form(request.user),
        },
    )


def _modal_body_from_request(request) -> str:
    raw = (
        request.POST.get("modal_body") or request.GET.get("modal_body") or "bookingModalBody"
    ).strip()
    if not raw.replace("_", "").isalnum():
        return "bookingModalBody"
    return raw


@htmx_login_required
@require_http_methods(["POST"])
def booking_submit(request, slug, slot_id):
    station = get_object_or_404(_active_station_queryset(), slug=slug)
    today = timezone.localdate()
    if not station_accepts_online_booking(station, today):
        return render(
            request,
            "stations/partials/booking_subscription_paused.html",
            {"station": station},
            status=403,
        )
    slot = get_object_or_404(TimeSlot, pk=slot_id, bay__station=station)
    modal_body = _modal_body_from_request(request)
    if not acquire_or_refresh_slot_hold(slot.pk, request.user.pk):
        return render(
            request,
            "stations/partials/booking_unavailable.html",
            {"station": station},
            status=409,
        )
    form = BookingRequestForm(request.POST, slot=slot, booking_user=request.user)
    if form.is_valid():
        try:
            create_booking_request(
                client=request.user,
                slot_id=slot.pk,
                car_info=form.cleaned_data["car_info"],
                contact_phone=form.cleaned_data["contact_phone"],
                description=form.cleaned_data["description"],
                request=request,
            )
        except SlotNotBookableError:
            messages.error(request, "Окно уже недоступно для записи.")
            return render(
                request,
                "stations/partials/booking_unavailable.html",
                {"station": station},
                status=409,
            )
        except BookingSlotConflictError:
            form.add_error(
                None,
                "Окно только что заняли. Выберите другое время.",
            )
            return render(
                request,
                "stations/partials/booking_form.html",
                {
                    "form": form,
                    "station": station,
                    "slot": slot,
                    "booking_modal_body_id": modal_body,
                    "saved_cars": _saved_cars_for_booking_form(request.user),
                },
                status=409,
            )
        else:
            response = HttpResponse(status=204)
            response["HX-Redirect"] = reverse("stations:booking_success", kwargs={"slug": slug})
            return response
    return render(
        request,
        "stations/partials/booking_form.html",
        {
            "form": form,
            "station": station,
            "slot": slot,
            "booking_modal_body_id": modal_body,
            "saved_cars": _saved_cars_for_booking_form(request.user),
        },
        status=422,
    )


class BookingSuccessView(TemplateView):
    template_name = "stations/booking_success.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["station"] = get_object_or_404(
            ServiceStation.objects.visible_in_catalog(today=timezone.localdate()),
            slug=self.kwargs["slug"],
        )
        return ctx


class HomePageView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v_city = (self.request.session.get(VISITOR_CITY_SESSION_KEY) or "").strip() or None
        ctx.update(build_homepage_context(city_label=v_city))
        focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", "") or "").strip()
        city = (v_city or focus or "").strip()
        if city:
            ctx["seo_meta_description"] = clamp_seo_description(
                f"Запись в СТО и к частным мастерам в {city}. Свободные окна, отзывы, фильтры по услугам и марке авто. Онлайн-запись за пару минут — МаБибип."
            )
            ctx["seo_og_title"] = f"МаБибип — запись в автосервис в {city}"
        else:
            ctx["seo_meta_description"] = clamp_seo_description(
                "Поиск СТО и частных мастеров рядом с вами: свободные слоты, отзывы, фильтры по услугам и марке авто. Онлайн-запись за пару минут. МаБибип."
            )
            ctx["seo_og_title"] = "МаБибип — запись в СТО онлайн"
        return ctx
