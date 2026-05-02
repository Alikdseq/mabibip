from __future__ import annotations

from datetime import timedelta
import logging
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Avg, Count, F, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.core.seo import clamp_seo_description
from apps.stations.models import CarBrand, ServiceStation
from apps.users.display import user_display_name
from apps.users.email_verification_access import EmailVerificationRequiredMixin, require_verified_email
from apps.users.onboarding_access import CompletedProfileRequiredMixin, require_completed_profile

from apps.chat.models import AdDirectThread, StationDirectThread
from apps.billing.models import ClassifiedsDeal, WalletLedgerEntry
from apps.billing.deal_services import ensure_wallet, ledger_idempotent, mark_buyer_confirmed, release_deal_funds
from apps.billing.yookassa_api import YooKassaError, create_payment, create_refund
from .call_ui import build_ad_call_context
from .forms import AdForm, AdUnpublishForm, SellerReviewForm
from .models import (
    Ad,
    AdCallClickEvent,
    AdCondition,
    AdKind,
    AdPhoto,
    AdReport,
    AutoShopBranch,
    AutoShopProfile,
    FavoriteShop,
    CarBodyType,
    CarDrive,
    CarFuel,
    CarTransmission,
    FavoriteAd,
    PartCategory,
    SellerReview,
    SellerReviewModerationStatus,
    seller_review_done_owner_ids_for_user,
)
from .tasks import compute_ad_photo_hash

MAX_PHOTOS_PER_AD = 15

logger = logging.getLogger(__name__)


def _schedule_compute_ad_photo_hash(photo_id: int) -> None:
    """Не ломать сохранение объявления, если Redis/Celery временно недоступны."""
    try:
        compute_ad_photo_hash.delay(int(photo_id))
    except Exception:
        logger.exception(
            "Не удалось поставить в очередь compute_ad_photo_hash (photo_id=%s)",
            photo_id,
        )

_AD_DETAIL_VIEWED_SESSION_KEY = "classifieds_ad_detail_viewed_pks"


def _bump_ad_detail_view_count(request, ad: Ad) -> None:
    """+1 к просмотрам для опубликованного объявления, не чаще одного раза на pk за сессию."""
    if not ad.pk or not ad.is_published:
        return
    viewed = request.session.get(_AD_DETAIL_VIEWED_SESSION_KEY)
    if not isinstance(viewed, list):
        viewed = []
    if ad.pk in viewed:
        return
    Ad.objects.filter(pk=ad.pk).update(view_count=F("view_count") + 1)
    request.session[_AD_DETAIL_VIEWED_SESSION_KEY] = viewed + [ad.pk]
    request.session.modified = True


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().casefold())


@lru_cache(maxsize=1)
def _car_models_by_brand_name() -> dict[str, list[str]]:
    """
    Парсим справочник моделей из корня репозитория `моделиавто.txt`.
    Формат — человекочитаемый: бренды помечены строками вида "🚗 BMW".
    """
    base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    p = base / "моделиавто.txt"
    if not p.exists():
        return {}
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return {}

    brands: dict[str, list[str]] = {}
    current: str | None = None
    bucket: list[str] = []

    def _flush():
        nonlocal bucket, current
        if not current:
            bucket = []
            return
        joined = " ".join(bucket)
        # заменяем большинство разделителей на запятую и режем
        cleaned = re.sub(r"[•;]", ",", joined)
        cleaned = re.sub(r"[()\[\]{}]", " ", cleaned)
        parts = [x.strip(" .\t\r\n") for x in cleaned.split(",")]
        out: list[str] = []
        seen = set()
        for item in parts:
            if not item:
                continue
            # выкидываем явный "мусор" заголовков
            low = item.casefold()
            if any(
                k in low
                for k in (
                    "серия",
                    "модели",
                    "кроссоверы",
                    "внедорожники",
                    "коммерческие",
                    "электрические",
                    "универсалы",
                    "купе",
                    "спорткары",
                    "и другие",
                    "и др",
                )
            ):
                continue
            # разумная длина модели
            if len(item) > 48:
                continue
            key = _norm_key(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        brands[_norm_key(current)] = out
        bucket = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("🚗"):
            _flush()
            current = line.replace("🚗", "").strip()
            continue
        if current:
            bucket.append(line)
    _flush()
    return brands


def _car_models_by_brand_id(brand_choices: list[CarBrand]) -> dict[str, list[str]]:
    by_name = _car_models_by_brand_name()
    out: dict[str, list[str]] = {}
    for b in brand_choices:
        key = _norm_key(b.name)
        models = by_name.get(key) or []
        out[str(b.pk)] = models
    return out


def _parse_opt_int(get, key: str, *, min_v: int | None = None, max_v: int | None = None) -> int | None:
    raw = (get.get(key) or "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    if min_v is not None and v < min_v:
        return None
    if max_v is not None and v > max_v:
        return None
    return v


def _parse_opt_brand_id(get, key: str) -> int | None:
    return _parse_opt_int(get, key, min_v=1)


def _enum_filter_ok(raw: str, enum_cls) -> bool:
    val = (raw or "").strip()
    if not val:
        return False
    return val in {c[0] for c in enum_cls.choices}


def _ad_photos_prefetch() -> Prefetch:
    return Prefetch("photos", queryset=AdPhoto.objects.order_by("order", "pk"))


def _car_advanced_filters_active(g) -> bool:
    """Есть ли активные «дополнительные» фильтры (всё кроме марки/модели/цены/года)."""
    if (g.get("sort") or "new").strip() not in ("", "new"):
        return True
    for key in (
        "q",
        "city",
        "mileage_min",
        "mileage_max",
        "car_transmission",
        "car_fuel",
        "car_drive",
        "car_body",
        "car_not_crashed",
    ):
        if (g.get(key) or "").strip():
            return True
    return False


class AdsListView(ListView):
    model = Ad
    template_name = "classifieds/ads_list.html"
    context_object_name = "ads"
    paginate_by = 24

    def get_queryset(self):
        g = self.request.GET
        tab = (g.get("tab") or AdKind.PART).strip()
        if tab not in (AdKind.PART, AdKind.CAR):
            tab = AdKind.PART

        qs = (
            Ad.objects.filter(is_published=True, kind=tab)
            .select_related("owner", "shop", "call_proxy")
            .prefetch_related(_ad_photos_prefetch())
        )

        q = (g.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

        city = (g.get("city") or "").strip()
        if city:
            qs = qs.filter(city_label__iexact=city)

        price_min = _parse_opt_int(g, "price_min", min_v=0)
        price_max = _parse_opt_int(g, "price_max", min_v=0)
        if price_min is not None:
            qs = qs.filter(price__gte=price_min)
        if price_max is not None:
            qs = qs.filter(price__lte=price_max)

        if tab == AdKind.PART:
            cat = (g.get("cat") or "").strip()
            if cat:
                qs = qs.filter(part_category__slug=cat)
            cond = (g.get("condition") or "").strip()
            if cond in (AdCondition.NEW, AdCondition.USED):
                qs = qs.filter(condition=cond)
            pb = _parse_opt_brand_id(g, "part_brand")
            if pb is not None and CarBrand.objects.filter(pk=pb).exists():
                qs = qs.filter(part_brand_id=pb)
        else:
            cb = _parse_opt_brand_id(g, "car_brand")
            if cb is not None and CarBrand.objects.filter(pk=cb).exists():
                qs = qs.filter(car_brand_id=cb)
            cm = (g.get("car_model") or "").strip()
            if cm:
                qs = qs.filter(car_model__icontains=cm)
            y_min = _parse_opt_int(g, "year_min", min_v=1950, max_v=2100)
            y_max = _parse_opt_int(g, "year_max", min_v=1950, max_v=2100)
            if y_min is not None:
                qs = qs.filter(car_year__gte=y_min)
            if y_max is not None:
                qs = qs.filter(car_year__lte=y_max)
            mile_min = _parse_opt_int(g, "mileage_min", min_v=0)
            mile_max = _parse_opt_int(g, "mileage_max", min_v=0)
            if mile_min is not None:
                qs = qs.filter(car_mileage_km__gte=mile_min)
            if mile_max is not None:
                qs = qs.filter(car_mileage_km__lte=mile_max)
            ct = (g.get("car_transmission") or "").strip()
            if _enum_filter_ok(ct, CarTransmission):
                qs = qs.filter(car_transmission=ct)
            cf = (g.get("car_fuel") or "").strip()
            if _enum_filter_ok(cf, CarFuel):
                qs = qs.filter(car_fuel=cf)
            cd = (g.get("car_drive") or "").strip()
            if _enum_filter_ok(cd, CarDrive):
                qs = qs.filter(car_drive=cd)
            cbody = (g.get("car_body") or "").strip()
            if _enum_filter_ok(cbody, CarBodyType):
                qs = qs.filter(car_body_type=cbody)
            nc = (g.get("car_not_crashed") or "").strip().lower()
            if nc in ("1", "true", "yes"):
                qs = qs.filter(car_not_crashed=True)
            elif nc in ("0", "false", "no"):
                qs = qs.filter(car_not_crashed=False)

        sort = (g.get("sort") or "new").strip()
        if sort == "price_asc":
            qs = qs.order_by("price", "-created_at", "-pk")
        elif sort == "price_desc":
            qs = qs.order_by("-price", "-created_at", "-pk")
        else:
            qs = qs.order_by("-created_at", "-pk")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        g = self.request.GET
        request = self.request
        tab = (g.get("tab") or AdKind.PART).strip()
        if tab not in (AdKind.PART, AdKind.CAR):
            tab = AdKind.PART

        ctx["tab"] = tab
        ctx["part_categories"] = list(PartCategory.objects.order_by("sort_order", "name"))
        car_brands = list(CarBrand.objects.order_by("-is_popular", "sort_order", "name"))
        ctx["car_brand_choices"] = car_brands
        ctx["q"] = (g.get("q") or "").strip()
        ctx["city"] = (g.get("city") or "").strip()
        ctx["cat"] = (g.get("cat") or "").strip()
        ctx["condition"] = (g.get("condition") or "").strip()
        ctx["part_brand"] = (g.get("part_brand") or "").strip()
        ctx["car_brand"] = (g.get("car_brand") or "").strip()
        ctx["car_model"] = (g.get("car_model") or "").strip()
        ctx["year_min"] = (g.get("year_min") or "").strip()
        ctx["year_max"] = (g.get("year_max") or "").strip()
        ctx["mileage_min"] = (g.get("mileage_min") or "").strip()
        ctx["mileage_max"] = (g.get("mileage_max") or "").strip()
        ctx["price_min"] = (g.get("price_min") or "").strip()
        ctx["price_max"] = (g.get("price_max") or "").strip()
        ctx["sort"] = (g.get("sort") or "new").strip()
        ctx["car_transmission"] = (g.get("car_transmission") or "").strip()
        ctx["car_fuel"] = (g.get("car_fuel") or "").strip()
        ctx["car_drive"] = (g.get("car_drive") or "").strip()
        ctx["car_body"] = (g.get("car_body") or "").strip()
        ctx["car_not_crashed"] = (g.get("car_not_crashed") or "").strip()

        qp = g.copy()
        if "page" in qp:
            del qp["page"]
        ctx["filter_query"] = qp.urlencode()

        if "paginator" in ctx:
            ctx["ads_total"] = ctx["paginator"].count
            ctx["filtered_total"] = ctx["paginator"].count
        else:
            ctx["ads_total"] = 0
            ctx["filtered_total"] = 0
        ctx["ads_mobile_two_column"] = ctx["filtered_total"] >= 50

        popular_cars = (
            CarBrand.objects.filter(car_ads__is_published=True, car_ads__kind=AdKind.CAR)
            .annotate(ad_count=Count("car_ads", distinct=True))
            .filter(ad_count__gt=0)
            .order_by("-ad_count", "name")[:16]
        )
        ctx["popular_car_brands"] = list(popular_cars)

        popular_parts = (
            PartCategory.objects.filter(ads__is_published=True, ads__kind=AdKind.PART)
            .annotate(ad_count=Count("ads", distinct=True))
            .filter(ad_count__gt=0)
            .order_by("-ad_count", "sort_order", "name")[:16]
        )
        ctx["popular_part_categories"] = list(popular_parts)

        ctx["car_transmission_choices"] = CarTransmission.choices
        ctx["car_fuel_choices"] = CarFuel.choices
        ctx["car_drive_choices"] = CarDrive.choices
        ctx["car_body_choices"] = CarBodyType.choices
        ctx["car_advanced_filters_active"] = _car_advanced_filters_active(g)
        ctx["car_models_by_brand_id"] = _car_models_by_brand_id(car_brands)

        title = "Объявления авто"
        if tab == AdKind.PART:
            title = "Автозапчасти — объявления"
        elif tab == AdKind.CAR:
            title = "Автомобили — объявления"
        ctx["seo_og_title"] = f"{title} — МаБибип"
        ctx["seo_meta_description"] = clamp_seo_description(
            "Объявления по автозапчастям и автомобилям на МаБибип: поиск, фильтры по городу, цене и характеристикам.",
            max_len=160,
        )
        ctx["ad_call_map"] = {
            a.pk: build_ad_call_context(request=self.request, ad=a) for a in ctx.get("ads", []) or []
        }

        page_ads = list(ctx.get("ads", []) or [])
        fav_ids: set[int] = set()
        if request.user.is_authenticated and page_ads:
            fav_ids = set(
                FavoriteAd.objects.filter(user=request.user, ad_id__in=[a.pk for a in page_ads]).values_list(
                    "ad_id",
                    flat=True,
                )
            )
        ctx["favorite_ad_ids"] = fav_ids
        ctx["seller_review_done_owner_ids"] = seller_review_done_owner_ids_for_user(
            request.user,
            (a.owner_id for a in page_ads),
        )
        return ctx


class AdDetailView(DetailView):
    model = Ad
    template_name = "classifieds/ad_detail.html"
    context_object_name = "ad"

    def get_queryset(self):
        return (
            Ad.objects.filter(is_published=True)
            .select_related("owner", "shop", "part_category", "part_brand", "car_brand", "call_proxy")
            .prefetch_related(_ad_photos_prefetch())
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        _bump_ad_detail_view_count(request, self.object)
        self.object.refresh_from_db(fields=["view_count"])
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ad = self.object
        request = self.request
        ctx["seo_og_title"] = f"{ad.title} — объявления — МаБибип"
        ctx["seo_meta_description"] = clamp_seo_description(ad.description or ad.title, max_len=160)
        photos = list(ad.photos.all())
        if photos:
            try:
                ctx["seo_og_image"] = request.build_absolute_uri(photos[0].image.url)
            except Exception:
                pass

        ctx["ad_call"] = build_ad_call_context(request=request, ad=ad)
        ctx["is_favorite_ad"] = request.user.is_authenticated and FavoriteAd.objects.filter(
            user=request.user,
            ad=ad,
        ).exists()
        ctx["has_reported"] = (
            request.user.is_authenticated
            and request.user.pk != ad.owner_id
            and AdReport.objects.filter(ad=ad, reported_by=request.user).exists()
        )
        ctx["ad_favorite_count"] = FavoriteAd.objects.filter(ad=ad).count()
        ctx["can_review_seller"] = (
            request.user.is_authenticated
            and request.user.pk != ad.owner_id
            and not SellerReview.objects.filter(author=request.user, seller_id=ad.owner_id).exists()
        )

        similar = Ad.objects.filter(is_published=True, kind=ad.kind).exclude(pk=ad.pk)
        if ad.kind == AdKind.PART and ad.part_category_id:
            similar = similar.filter(part_category_id=ad.part_category_id)
        elif ad.kind == AdKind.CAR and ad.car_brand_id:
            similar = similar.filter(car_brand_id=ad.car_brand_id)
        similar_qs = (
            similar.select_related("owner", "shop", "call_proxy")
            .prefetch_related(_ad_photos_prefetch())
            .order_by("-created_at", "-pk")[:8]
        )
        ctx["similar_ads"] = list(similar_qs)
        ctx["similar_ad_call_map"] = {
            a.pk: build_ad_call_context(request=request, ad=a) for a in ctx["similar_ads"]
        }
        sim_ads = ctx["similar_ads"]
        if request.user.is_authenticated and sim_ads:
            ctx["similar_favorite_ad_ids"] = set(
                FavoriteAd.objects.filter(
                    user=request.user,
                    ad_id__in=[a.pk for a in sim_ads],
                ).values_list("ad_id", flat=True)
            )
        else:
            ctx["similar_favorite_ad_ids"] = set()
        ctx["similar_seller_review_done_owner_ids"] = seller_review_done_owner_ids_for_user(
            request.user,
            (a.owner_id for a in sim_ads),
        )
        ctx["login_next_qs"] = quote(request.get_full_path() or "/", safe="/")
        ctx["seller_public_ads_count"] = Ad.objects.filter(is_published=True, owner_id=ad.owner_id).count()
        return ctx


@login_required
def favorite_ad_toggle(request, pk: int):
    ad = get_object_or_404(Ad.objects.filter(is_published=True), pk=pk)
    qs = FavoriteAd.objects.filter(user=request.user, ad=ad)
    was_fav = qs.exists()
    if qs.exists():
        qs.delete()
    else:
        FavoriteAd.objects.create(user=request.user, ad=ad)

    # HTMX: вернуть кнопку без редиректа (мгновенное переключение в списке)
    if (request.headers.get("HX-Request") or "").lower() == "true":
        is_fav = not was_fav
        use_icon = (request.POST.get("use_icon") or "").strip() == "1"
        tmpl = (
            "classifieds/partials/favorite_ad_button_icon.html"
            if use_icon
            else "classifieds/partials/favorite_ad_button.html"
        )
        return render(request, tmpl, {"ad": ad, "is_favorite": is_fav})

    next_url = (request.POST.get("next") or "").strip() or request.META.get("HTTP_REFERER") or ""
    if next_url:
        # Без уведомлений: просто возвращаем пользователя назад.
        return redirect(next_url)
    return redirect(reverse("classifieds:ad_detail", kwargs={"pk": ad.pk}))


def _seller_review_redirect(request, seller):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(reverse("classifieds:seller_profile", kwargs={"public_id": seller.public_id}))


@login_required
@require_http_methods(["GET", "POST"])
def seller_review_create(request, public_id):
    User = get_user_model()
    seller = get_object_or_404(User.objects.all(), public_id=public_id)
    if request.user.pk == seller.pk:
        messages.error(request, "Нельзя оставить отзыв самому себе.")
        return redirect(reverse("classifieds:seller_profile", kwargs={"public_id": seller.public_id}))
    if SellerReview.objects.filter(author=request.user, seller=seller).exists():
        messages.info(request, "Вы уже оставили отзыв этому продавцу.")
        return _seller_review_redirect(request, seller)

    next_raw = (request.POST.get("next") or request.GET.get("next") or "").strip()

    if request.method == "POST":
        form = SellerReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.author = request.user
            review.seller = seller
            try:
                review.save()
            except IntegrityError:
                messages.warning(
                    request,
                    "Отзыв уже был сохранён. Если страница открыта в нескольких вкладках, обновите её.",
                )
                return _seller_review_redirect(request, seller)
            messages.success(request, "Спасибо, ваш отзыв сохранён.")
            return _seller_review_redirect(request, seller)
    else:
        form = SellerReviewForm()

    return render(
        request,
        "classifieds/seller_review_form.html",
        {
            "seller": seller,
            "form": form,
            "review_next_url": next_raw,
        },
    )


class SellerProfileView(DetailView):
    """
    Публичный профиль продавца (как Avito): все его опубликованные объявления.
    Используем UUID `User.public_id`, чтобы не светить числовые id.
    """

    template_name = "classifieds/seller_profile.html"
    context_object_name = "seller"

    def get_queryset(self):
        User = get_user_model()
        return User.objects.all()

    def get_object(self, queryset=None):
        qs = queryset or self.get_queryset()
        return get_object_or_404(qs, public_id=self.kwargs.get("public_id"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        seller = ctx["seller"]
        request = self.request
        ads = (
            Ad.objects.filter(owner=seller, is_published=True)
            .select_related("owner", "shop", "call_proxy")
            .prefetch_related(_ad_photos_prefetch())
            .order_by("-created_at", "-pk")
        )
        ctx["ads"] = list(ads[:48])
        ctx["ads_total"] = ads.count()
        ctx["seo_og_title"] = "Профиль продавца — объявления — МаБибип"
        ctx["seo_meta_description"] = clamp_seo_description(
            "Публичный профиль продавца: все объявления пользователя на МаБибип.",
            max_len=160,
        )
        ctx["ad_call_map"] = {a.pk: build_ad_call_context(request=request, ad=a) for a in ctx["ads"]}
        fav_ids: set[int] = set()
        if request.user.is_authenticated and ctx["ads"]:
            fav_ids = set(
                FavoriteAd.objects.filter(user=request.user, ad_id__in=[a.pk for a in ctx["ads"]]).values_list(
                    "ad_id",
                    flat=True,
                )
            )
        ctx["favorite_ad_ids"] = fav_ids
        ctx["ads_mobile_two_column"] = ctx["ads_total"] >= 50
        ctx["seller_review_done_owner_ids"] = seller_review_done_owner_ids_for_user(
            request.user,
            (a.owner_id for a in ctx["ads"]),
        )

        ok_status = SellerReviewModerationStatus.OK
        rev_qs = SellerReview.objects.filter(seller=seller, moderation_status=ok_status).select_related(
            "author",
        )
        ctx["seller_reviews"] = list(rev_qs.order_by("-created_at", "-pk")[:50])
        agg = rev_qs.aggregate(avg_rating=Avg("rating"), n=Count("id"))
        ctx["seller_review_avg"] = agg["avg_rating"]
        ctx["seller_review_count"] = agg["n"] or 0
        ctx["can_review_seller_on_profile"] = (
            request.user.is_authenticated
            and request.user.pk != seller.pk
            and not SellerReview.objects.filter(author=request.user, seller=seller).exists()
        )
        ctx["seller_display_name"] = user_display_name(seller, fallback="Пользователь")
        return ctx


class ShopDetailView(DetailView):
    model = AutoShopProfile
    slug_url_kwarg = "slug"
    template_name = "classifieds/shop_detail.html"
    context_object_name = "shop"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        shop = self.object
        ctx["branches"] = list(AutoShopBranch.objects.filter(shop=shop).order_by("name", "pk"))
        ctx["is_favorite_shop"] = bool(
            self.request.user.is_authenticated
            and FavoriteShop.objects.filter(user=self.request.user, shop=shop).exists()
        )
        ctx["ads"] = (
            Ad.objects.filter(shop=shop, is_published=True)
            .prefetch_related(_ad_photos_prefetch())
            .order_by("-created_at", "-pk")[:36]
        )
        ctx["seo_og_title"] = f"{shop.name} — объявления — МаБибип"
        desc = (shop.description or "").strip()
        if not desc:
            desc = f"Профиль автомагазина {shop.name}. Объявления по автозапчастям и автомобилям."
        ctx["seo_meta_description"] = clamp_seo_description(desc, max_len=160)
        return ctx


class ShopListView(ListView):
    model = AutoShopProfile
    template_name = "classifieds/shops_list.html"
    context_object_name = "shops"
    paginate_by = 24

    def get_queryset(self):
        qs = AutoShopProfile.objects.all().order_by("name", "pk")
        kind = (self.request.GET.get("kind") or "").strip()
        if kind in {AutoShopProfile.Kind.SHOP, AutoShopProfile.Kind.DISMANTLE, AutoShopProfile.Kind.DEALER}:
            qs = qs.filter(kind=kind)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        city = (self.request.GET.get("city") or "").strip()
        if city:
            qs = qs.filter(city_label__iexact=city)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        kind = (self.request.GET.get("kind") or "").strip()
        if kind not in {AutoShopProfile.Kind.SHOP, AutoShopProfile.Kind.DISMANTLE, AutoShopProfile.Kind.DEALER}:
            kind = AutoShopProfile.Kind.SHOP
        ctx["kind"] = kind
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["city"] = (self.request.GET.get("city") or "").strip()
        ctx["seo_og_title"] = "Автомагазины, разборки и автосалоны — МаБибип"
        ctx["seo_meta_description"] = clamp_seo_description(
            "Каталог автомагазинов, разборок и автосалонов. Выберите тип и найдите продавца по названию и городу.",
            max_len=160,
        )
        return ctx


class MyAdsListView(LoginRequiredMixin, ListView):
    model = Ad
    template_name = "classifieds/my_ads_list.html"
    context_object_name = "ads"
    paginate_by = 30

    def get_queryset(self):
        return Ad.objects.filter(owner=self.request.user).prefetch_related(_ad_photos_prefetch()).order_by(
            "-created_at", "-pk"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cabinet_section"] = "ads"
        return ctx


class MyDealsListView(LoginRequiredMixin, ListView):
    model = ClassifiedsDeal
    template_name = "classifieds/my_deals_list.html"
    context_object_name = "deals"
    paginate_by = 30

    def get_queryset(self):
        u = self.request.user
        return (
            ClassifiedsDeal.objects.select_related("ad")
            .filter(Q(buyer=u) | Q(seller=u))
            .order_by("-created_at", "-pk")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cabinet_section"] = "deals"
        return ctx


class DealDetailView(LoginRequiredMixin, DetailView):
    model = ClassifiedsDeal
    template_name = "classifieds/deal_detail.html"
    context_object_name = "deal"

    def get_queryset(self):
        u = self.request.user
        return ClassifiedsDeal.objects.select_related("ad").filter(Q(buyer=u) | Q(seller=u))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cabinet_section"] = "deals"
        return ctx


class MyAdCreateView(LoginRequiredMixin, CompletedProfileRequiredMixin, CreateView):
    model = Ad
    form_class = AdForm
    template_name = "classifieds/my_ad_form.html"
    success_url = reverse_lazy("classifieds:my_ads")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        ad = form.save(commit=False)
        ad.owner = self.request.user
        shop = getattr(self.request.user, "autoshop_profile", None)
        if shop:
            ad.shop = shop
        ad.save()
        photos = (form.cleaned_data.get("photos") or [])[:MAX_PHOTOS_PER_AD]
        if photos:
            for i, f in enumerate(photos):
                ph = AdPhoto.objects.create(ad=ad, image=f, order=i)
                pid = int(ph.pk)
                transaction.on_commit(lambda photo_id=pid: _schedule_compute_ad_photo_hash(photo_id))
        messages.success(self.request, "Объявление создано.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cabinet_section"] = "ads"
        return ctx


class MyAdUpdateView(LoginRequiredMixin, CompletedProfileRequiredMixin, UpdateView):
    model = Ad
    form_class = AdForm
    template_name = "classifieds/my_ad_form.html"
    success_url = reverse_lazy("classifieds:my_ads")

    def get_queryset(self):
        return Ad.objects.filter(owner=self.request.user)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        resp = super().form_valid(form)
        room = max(0, MAX_PHOTOS_PER_AD - int(self.object.photos.count()))
        photos = (form.cleaned_data.get("photos") or [])[:room]
        if photos:
            start = int(self.object.photos.count())
            for i, f in enumerate(photos):
                ph = AdPhoto.objects.create(ad=self.object, image=f, order=start + i)
                pid = int(ph.pk)
                transaction.on_commit(lambda photo_id=pid: _schedule_compute_ad_photo_hash(photo_id))
        messages.success(self.request, "Объявление сохранено.")
        return resp


class MyAdUnpublishView(LoginRequiredMixin, FormView):
    template_name = "classifieds/ad_unpublish.html"
    form_class = AdUnpublishForm

    def dispatch(self, request, *args, **kwargs):
        self.ad = get_object_or_404(Ad, pk=int(kwargs.get("pk")), owner=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ad"] = self.ad
        ctx["next"] = (self.request.GET.get("next") or "").strip()
        return ctx

    def form_valid(self, form):
        if not self.ad.is_published:
            messages.info(self.request, "Объявление уже снято с публикации.")
            return redirect(self.get_success_url())

        self.ad.is_published = False
        self.ad.unpublished_at = timezone.now()
        self.ad.unpublish_reason = form.cleaned_data["reason"]
        self.ad.unpublish_reason_text = (form.cleaned_data.get("reason_text") or "")[:300]
        self.ad.save(
            update_fields=[
                "is_published",
                "unpublished_at",
                "unpublish_reason",
                "unpublish_reason_text",
            ]
        )
        messages.success(self.request, "Объявление снято с публикации.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        nxt = (self.request.POST.get("next") or self.request.GET.get("next") or "").strip()
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={self.request.get_host()}):
            return nxt
        return reverse("classifieds:my_ads")


@login_required
@require_POST
def ad_call_click_log(request, pk: int):
    """Учёт нажатия «Позвонить» (клиент с реальным tel:, не автор объявления)."""
    ad = get_object_or_404(Ad, pk=pk, is_published=True)
    if ad.owner_id == request.user.pk:
        return HttpResponse(status=204)
    AdCallClickEvent.objects.create(ad=ad, ad_kind=ad.kind, user=request.user)
    return HttpResponse(status=204)


@login_required
@require_completed_profile
def ad_start_chat(request, pk: int):
    """«Написать» по объявлению: чат покупатель ↔ продавец (AdDirectThread)."""
    ad = get_object_or_404(Ad.objects.select_related("owner"), pk=pk, is_published=True)
    if ad.owner_id == request.user.pk:
        messages.info(request, "Это ваше объявление.")
        return redirect("classifieds:ad_detail", pk=ad.pk)

    thread, _ = AdDirectThread.objects.get_or_create(ad=ad, buyer=request.user, defaults={"seller": ad.owner})
    return redirect("cabinet:ad_direct_chat_detail", thread_id=thread.pk)


@login_required
@require_completed_profile
@require_POST
def ad_safe_buy_start(request, pk: int):
    """
    «Безопасная сделка» (MVP): создаём сделку и платёж ЮKassa.
    Деньги считаем «на холде» после webhook payment.succeeded.
    """
    ad = get_object_or_404(Ad.objects.select_related("owner"), pk=int(pk), is_published=True)
    if ad.owner_id == request.user.pk:
        messages.info(request, "Нельзя купить своё объявление.")
        return redirect("classifieds:ad_detail", pk=ad.pk)

    deal = (
        ClassifiedsDeal.objects.filter(ad=ad, buyer=request.user, seller=ad.owner)
        .exclude(status__in=[ClassifiedsDeal.Status.CANCELED, ClassifiedsDeal.Status.REFUNDED, ClassifiedsDeal.Status.RELEASED])
        .order_by("-created_at", "-pk")
        .first()
    )
    if not deal:
        deal = ClassifiedsDeal.objects.create(
            ad=ad,
            buyer=request.user,
            seller=ad.owner,
            amount=ad.price,
            currency="RUB",
            status=ClassifiedsDeal.Status.PAYMENT_PENDING,
            delivery_kind=ClassifiedsDeal.DeliveryKind.MEETUP,
        )
    elif deal.status == ClassifiedsDeal.Status.CREATED:
        deal.status = ClassifiedsDeal.Status.PAYMENT_PENDING
        deal.save(update_fields=["status"])

    if not getattr(settings, "YOOKASSA_ENABLED", False):
        messages.warning(request, "Оплата через ЮKassa пока отключена администратором.")
        return redirect("classifieds:ad_detail", pk=ad.pk)

    return_url = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/") + reverse("classifieds:ad_detail", args=[ad.pk])
    try:
        resp = create_payment(
            amount=deal.amount,
            currency=deal.currency,
            description=f"Безопасная сделка по объявлению #{ad.pk} (МаБибип)",
            return_url=return_url,
            metadata={"deal_id": str(deal.pk), "ad_id": str(ad.pk)},
            idempotency_key=f"deal-{deal.pk}",
        )
    except YooKassaError as e:
        messages.error(request, f"Не удалось создать платёж: {e}")
        return redirect("classifieds:ad_detail", pk=ad.pk)

    deal.provider_payload = resp or {}
    provider_payment_id = str((resp or {}).get("id") or "")
    if provider_payment_id and not deal.provider_payment_id:
        deal.provider_payment_id = provider_payment_id
    deal.save(update_fields=["provider_payload", "provider_payment_id"])

    confirmation_url = ((resp or {}).get("confirmation") or {}).get("confirmation_url") if isinstance((resp or {}).get("confirmation"), dict) else ""
    if confirmation_url:
        return redirect(confirmation_url)
    messages.error(request, "Провайдер не вернул ссылку для оплаты.")
    return redirect("classifieds:ad_detail", pk=ad.pk)


@login_required
@require_POST
def classifieds_deal_cancel(request, deal_id: int):
    """
    Отмена сделки покупателем до отправки.
    Если платёж уже прошёл — делаем refund через ЮKassa (MVP).
    """
    deal = get_object_or_404(
        ClassifiedsDeal.objects.select_related("ad"),
        pk=int(deal_id),
        buyer=request.user,
    )

    if deal.status not in {
        ClassifiedsDeal.Status.CREATED,
        ClassifiedsDeal.Status.PAYMENT_PENDING,
        ClassifiedsDeal.Status.WAITING_SHIPMENT,
        ClassifiedsDeal.Status.FUNDS_HELD,
    }:
        messages.info(request, "Сделку нельзя отменить на текущем этапе.")
        return redirect("classifieds:ad_detail", pk=deal.ad_id)

    if deal.status in {ClassifiedsDeal.Status.CREATED, ClassifiedsDeal.Status.PAYMENT_PENDING} and not deal.paid_at:
        deal.status = ClassifiedsDeal.Status.CANCELED
        deal.canceled_at = timezone.now()
        deal.save(update_fields=["status", "canceled_at"])
        messages.success(request, "Сделка отменена.")
        return redirect("classifieds:ad_detail", pk=deal.ad_id)

    # Платёж был — делаем refund
    if not getattr(settings, "YOOKASSA_ENABLED", False):
        messages.error(request, "Возврат сейчас недоступен: интеграция оплаты отключена.")
        return redirect("classifieds:ad_detail", pk=deal.ad_id)

    if not deal.provider_payment_id:
        messages.error(request, "Не найден платеж провайдера для возврата.")
        return redirect("classifieds:ad_detail", pk=deal.ad_id)

    try:
        refund_resp = create_refund(
            payment_id=deal.provider_payment_id,
            amount=deal.amount,
            currency=deal.currency,
            description=f"Отмена сделки #{deal.pk} (МаБибип)",
            metadata={"deal_id": str(deal.pk), "ad_id": str(deal.ad_id)},
            idempotency_key=f"refund-deal-{deal.pk}",
        )
    except YooKassaError as e:
        messages.error(request, f"Не удалось оформить возврат: {e}")
        return redirect("classifieds:ad_detail", pk=deal.ad_id)

    deal.provider_payload = {"payment": deal.provider_payload, "refund": refund_resp}
    deal.status = ClassifiedsDeal.Status.REFUND_PENDING
    deal.save(update_fields=["provider_payload", "status"])

    refund_id = str((refund_resp or {}).get("id") or "")
    refund_status = str((refund_resp or {}).get("status") or "")

    # Уменьшаем холд продавца (если он уже есть) — идемпотентно по refund_id.
    if refund_id:
        w = ensure_wallet(deal.seller_id)
        ledger_idempotent(
            wallet=w,
            kind=WalletLedgerEntry.Kind.DEAL_HOLD,
            direction=WalletLedgerEntry.Direction.DEBIT,
            amount=deal.amount,
            currency=deal.currency,
            external_id=refund_id,
            payload={"deal_id": deal.pk, "op": "refund", "provider_payment_id": deal.provider_payment_id},
        )

    if refund_status in {"succeeded", "success"}:
        deal.status = ClassifiedsDeal.Status.REFUNDED
        deal.canceled_at = timezone.now()
        deal.save(update_fields=["status", "canceled_at"])
        messages.success(request, "Сделка отменена, возврат оформлен.")
    else:
        messages.success(request, "Сделка отменена, возврат в обработке.")

    return redirect("classifieds:ad_detail", pk=deal.ad_id)


@login_required
@require_POST
def classifieds_deal_mark_shipped(request, deal_id: int):
    deal = get_object_or_404(ClassifiedsDeal, pk=int(deal_id), seller=request.user)
    if deal.status not in {ClassifiedsDeal.Status.WAITING_SHIPMENT, ClassifiedsDeal.Status.FUNDS_HELD}:
        messages.info(request, "Нельзя отметить отправку на текущем этапе.")
        return redirect("classifieds:deal_detail", pk=deal.pk)

    deal.status = ClassifiedsDeal.Status.SHIPPED
    deal.seller_marked_shipped_at = timezone.now()
    days = int(getattr(settings, "DEAL_AUTO_CONFIRM_DAYS", 7))
    deal.auto_confirm_at = deal.seller_marked_shipped_at + timedelta(days=days)
    deal.save(update_fields=["status", "seller_marked_shipped_at", "auto_confirm_at"])
    messages.success(request, "Отмечено как «Отправлено».")
    return redirect("classifieds:deal_detail", pk=deal.pk)


@login_required
@require_POST
def classifieds_deal_confirm_received(request, deal_id: int):
    deal = get_object_or_404(ClassifiedsDeal, pk=int(deal_id), buyer=request.user)
    if deal.status not in {ClassifiedsDeal.Status.WAITING_SHIPMENT, ClassifiedsDeal.Status.SHIPPED}:
        messages.info(request, "Нельзя подтвердить получение на текущем этапе.")
        return redirect("classifieds:deal_detail", pk=deal.pk)

    # Meetup может завершаться без «Отправлено»
    mark_buyer_confirmed(deal=deal)
    ext = (deal.provider_payment_id or "").strip() or f"deal-{deal.pk}"
    release_deal_funds(deal=deal, external_id=ext)
    messages.success(request, "Получение подтверждено. Средства доступны продавцу.")
    return redirect("classifieds:deal_detail", pk=deal.pk)


@login_required
@require_verified_email
def biz_products(request):
    # Backward-compat route: legacy link from STO cabinet.
    # For autoshop role we redirect to the dedicated autoshop cabinet.
    if getattr(request.user, "business_role", "") == "autoshop":
        return redirect("shop_owner:products")

    if not getattr(request.user, "is_sto_owner", False):
        raise Http404
    if getattr(request.user, "sto_moderation_status", "") != "approved":
        return redirect("sto_owner:pending_moderation")
    shop = getattr(request.user, "autoshop_profile", None)
    if not shop:
        messages.info(request, "Профиль автомагазина не настроен.")
        return redirect("sto_owner:dashboard")
    ads = Ad.objects.filter(shop=shop).prefetch_related(_ad_photos_prefetch()).order_by("-created_at", "-pk")
    return render(request, "classifieds/biz_products.html", {"ads": ads, "shop": shop})


@login_required
@require_verified_email
def ad_photo_delete(request, pk):
    if request.method != "POST":
        raise Http404
    ph = get_object_or_404(AdPhoto.objects.select_related("ad"), pk=pk)
    if ph.ad.owner_id != request.user.pk:
        raise Http404
    ad_id = ph.ad_id
    ph.delete()
    messages.success(request, "Фото удалено.")
    return redirect("classifieds:my_ad_edit", pk=ad_id)
