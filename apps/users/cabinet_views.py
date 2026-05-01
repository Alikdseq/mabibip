"""Личный кабинет клиента: записи, отзывы, профиль, авто, избранное (фаза B)."""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Prefetch
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.classifieds.models import (
    AdPhoto,
    FavoriteAd,
    SellerReview,
    SellerReviewModerationStatus,
    seller_review_done_owner_ids_for_user,
)
from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking
from apps.bookings.services import (
    client_accept_reschedule,
    client_cancel_booking,
    client_cancel_booking_precheck,
    client_decline_reschedule,
)
from apps.reviews.forms import ReviewForm
from apps.reviews.models import REVIEW_CLIENT_EDIT_HOURS, ModerationStatus, Review
from apps.support.models import SupportTicket
from apps.support.services import create_ticket_with_initial_message
from apps.support.unread import mark_ticket_read_by_user, support_unread_tickets_for_user_qs
from apps.stations.models import ServiceStation
from apps.users.cabinet_forms import ClientProfileForm, ContactPhoneChangeRequestForm, SavedCarForm
from apps.users.models import ContactPhoneChangeRequest
from apps.classifieds.models import AdPhoto, AutoShopProfile, FavoriteAd, FavoriteShop
from apps.users.models import FavoriteStation, SavedCar, User

logger = logging.getLogger(__name__)


class CabinetSectionMixin:
    """Передаёт имя раздела для поднавигации ЛК."""

    cabinet_section = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cabinet_section"] = self.cabinet_section
        return ctx


class CabinetHubView(CabinetSectionMixin, LoginRequiredMixin, TemplateView):
    """Точка входа в ЛК клиента: ссылки на разделы без привязки к одному из них."""

    template_name = "users/cabinet/hub.html"
    cabinet_section = "hub"


class ClientBookingListView(CabinetSectionMixin, LoginRequiredMixin, ListView):
    model = Booking
    template_name = "users/cabinet/booking_list.html"
    context_object_name = "bookings"
    cabinet_section = "bookings"

    def get_queryset(self):
        return (
            Booking.objects.filter(client=self.request.user)
            .select_related(
                "station",
                "slot",
                "slot__bay",
                "reschedule_proposed_slot",
                "reschedule_proposed_slot__bay",
            )
            .annotate(
                has_review=Exists(Review.objects.filter(booking_id=OuterRef("pk"))),
            )
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        cancelable = set()
        for b in ctx["bookings"]:
            msg = client_cancel_booking_precheck(b, u)
            if msg is None:
                cancelable.add(b.pk)
                b.client_cancel_hint = ""
            else:
                b.client_cancel_hint = msg
        ctx["cancelable_booking_ids"] = cancelable
        return ctx


@login_required
@require_POST
def client_booking_cancel(request, pk):
    booking = get_object_or_404(Booking.objects.filter(client=request.user), pk=pk)
    try:
        client_cancel_booking(booking=booking, client=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Запись отменена.")
    return redirect("cabinet:bookings")


@login_required
@require_POST
def client_booking_reschedule_accept(request, pk):
    booking = get_object_or_404(Booking.objects.filter(client=request.user), pk=pk)
    try:
        client_accept_reschedule(booking=booking, client=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    except Http404:
        raise
    else:
        messages.success(request, "Новое время подтверждено. Ждём вас на визите.")
    return redirect("cabinet:bookings")


@login_required
@require_POST
def client_booking_reschedule_decline(request, pk):
    booking = get_object_or_404(Booking.objects.filter(client=request.user), pk=pk)
    try:
        client_decline_reschedule(booking=booking, client=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    except Http404:
        raise
    else:
        messages.info(request, "Вы оставили прежнее время. Мастер увидит отказ в уведомлении.")
    return redirect("cabinet:bookings")


class ClientProfileView(CabinetSectionMixin, LoginRequiredMixin, UpdateView):
    form_class = ClientProfileForm
    template_name = "users/cabinet/profile.html"
    success_url = reverse_lazy("cabinet:profile")
    cabinet_section = "profile"

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        messages.success(self.request, "Профиль сохранён.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        ctx["contact_phone_pending_request"] = (
            ContactPhoneChangeRequest.objects.filter(user=u, status=ContactPhoneChangeRequest.Status.PENDING)
            .order_by("-created_at")
            .first()
        )
        return ctx


class ContactPhoneChangeRequestView(CabinetSectionMixin, LoginRequiredMixin, FormView):
    template_name = "users/cabinet/contact_phone_change.html"
    form_class = ContactPhoneChangeRequestForm
    success_url = reverse_lazy("cabinet:profile")
    cabinet_section = "profile"

    def dispatch(self, request, *args, **kwargs):
        if not (getattr(request.user, "contact_phone", "") or "").strip():
            messages.info(request, "Сначала укажите телефон для связи в профиле.")
            return redirect("cabinet:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        u = self.request.user
        pending = ContactPhoneChangeRequest.objects.filter(user=u, status=ContactPhoneChangeRequest.Status.PENDING).first()
        if pending:
            messages.info(self.request, "Заявка на смену телефона уже отправлена и находится на рассмотрении.")
            return redirect("cabinet:profile")

        new_phone_e164 = form.cleaned_data["new_phone"]
        ContactPhoneChangeRequest.objects.create(
            user=u,
            old_phone_e164=(u.contact_phone or "").strip(),
            new_phone_e164=new_phone_e164,
            reason=(form.cleaned_data.get("reason") or "").strip()[:500],
        )
        messages.success(self.request, "Заявка на смену телефона отправлена и будет рассмотрена администратором.")
        return super().form_valid(form)


class SavedCarListView(CabinetSectionMixin, LoginRequiredMixin, ListView):
    model = SavedCar
    template_name = "users/cabinet/saved_car_list.html"
    context_object_name = "cars"
    cabinet_section = "cars"

    def get_queryset(self):
        return SavedCar.objects.filter(user=self.request.user)


class SavedCarCreateView(CabinetSectionMixin, LoginRequiredMixin, CreateView):
    model = SavedCar
    form_class = SavedCarForm
    template_name = "users/cabinet/saved_car_form.html"
    success_url = reverse_lazy("cabinet:cars")
    cabinet_section = "cars"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Автомобиль добавлен.")
        try:
            with transaction.atomic():
                self.object = form.save()
        except IntegrityError:
            messages.error(self.request, "Авто с таким госномером уже есть в списке.")
            return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())


class SavedCarUpdateView(CabinetSectionMixin, LoginRequiredMixin, UpdateView):
    model = SavedCar
    form_class = SavedCarForm
    template_name = "users/cabinet/saved_car_form.html"
    success_url = reverse_lazy("cabinet:cars")
    cabinet_section = "cars"

    def get_queryset(self):
        return SavedCar.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Данные обновлены.")
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            messages.error(self.request, "Авто с таким госномером уже есть в списке.")
            return self.form_invalid(form)


class SavedCarDeleteView(CabinetSectionMixin, LoginRequiredMixin, DeleteView):
    model = SavedCar
    template_name = "users/cabinet/saved_car_confirm_delete.html"
    success_url = reverse_lazy("cabinet:cars")
    cabinet_section = "cars"

    def get_queryset(self):
        return SavedCar.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.info(self.request, "Автомобиль удалён из списка.")
        return super().form_valid(form)


class FavoritesHubView(CabinetSectionMixin, LoginRequiredMixin, TemplateView):
    template_name = "users/cabinet/favorites_hub.html"
    cabinet_section = "favorites"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = (self.request.GET.get("tab") or "stations").strip()
        allowed_tabs = {"stations", "ads", "shop", "dismantle", "dealer"}
        if tab not in allowed_tabs:
            tab = "stations"
        ctx["tab"] = tab

        if tab == "stations":
            ctx["favorite_stations"] = list(
                FavoriteStation.objects.filter(user=self.request.user)
                .select_related("station")
                .order_by("-created_at")
            )
            ctx["favorite_ads"] = []
            ctx["favorite_shops"] = []
            return ctx

        if tab == "ads":
            photos_prefetch = Prefetch("ad__photos", queryset=AdPhoto.objects.order_by("order", "pk"))
            fav_qs = (
                FavoriteAd.objects.filter(user=self.request.user)
                .select_related("ad", "ad__owner", "ad__shop", "ad__call_proxy")
                .prefetch_related(photos_prefetch)
                .order_by("-created_at", "-pk")
            )
            rows = list(fav_qs)
            ctx["favorite_ads"] = rows
            ctx["favorite_ad_ids"] = {r.ad_id for r in rows}
            ctx["ad_call_map"] = {}
            ctx["seller_review_done_owner_ids"] = seller_review_done_owner_ids_for_user(
                self.request.user,
                (r.ad.owner_id for r in rows if getattr(r, "ad", None)),
            )
            ctx["favorite_stations"] = []
            ctx["favorite_shops"] = []
            return ctx

        # shops tabs
        shop_kind = tab
        shop_kind_allowed = {k for k, _ in AutoShopProfile.Kind.choices}
        if shop_kind not in shop_kind_allowed:
            shop_kind = AutoShopProfile.Kind.SHOP
        ctx["favorite_shops"] = list(
            FavoriteShop.objects.filter(user=self.request.user, shop__kind=shop_kind)
            .select_related("shop")
            .order_by("-created_at", "-pk")
        )
        ctx["favorite_stations"] = []
        ctx["favorite_ads"] = []
        return ctx


@login_required
@require_POST
def favorite_shop_toggle(request, slug):
    shop = get_object_or_404(AutoShopProfile, slug=slug)
    qs = FavoriteShop.objects.filter(user=request.user, shop=shop)
    if qs.exists():
        qs.delete()
        messages.info(request, f"«{shop.name}» убрано из избранного.")
    else:
        FavoriteShop.objects.create(user=request.user, shop=shop)
        messages.success(request, f"«{shop.name}» в избранном.")
    return redirect(reverse("classifieds:shop_detail", kwargs={"slug": shop.slug}))


@login_required
@require_POST
def favorite_toggle(request, slug):
    station = get_object_or_404(
        ServiceStation.objects.filter(is_active=True),
        slug=slug,
    )
    qs = FavoriteStation.objects.filter(user=request.user, station=station)
    if qs.exists():
        qs.delete()
        messages.info(request, f"«{station.name}» убрано из избранного.")
    else:
        FavoriteStation.objects.create(user=request.user, station=station)
        messages.success(request, f"«{station.name}» в избранном.")
    return redirect(reverse("stations:detail", kwargs={"slug": station.slug}))


class ClientReviewListView(CabinetSectionMixin, LoginRequiredMixin, ListView):
    """Отзывы о вас: по записям/СТО и по продажам (объявления)."""

    model = Review
    template_name = "users/cabinet/review_list.html"
    context_object_name = "reviews"
    cabinet_section = "reviews"

    def get_queryset(self):
        return Review.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["review_edit_hours"] = REVIEW_CLIENT_EDIT_HOURS
        user = self.request.user
        br = getattr(user, "business_role", None)
        show_work = getattr(user, "is_sto_owner", False) or br in (
            User.BusinessRole.MASTER,
            User.BusinessRole.AUTOSERVICE,
            User.BusinessRole.AUTOSHOP,
        )
        work_qs = (
            Review.objects.filter(
                booking__station__owner=user,
                moderation_status=ModerationStatus.OK,
            )
            .select_related("booking", "booking__station", "booking__client")
            .order_by("-created_at")
        )
        ctx["reviews_work"] = list(work_qs[:100]) if show_work else []
        ctx["reviews_sales"] = list(
            SellerReview.objects.filter(
                seller=user,
                moderation_status=SellerReviewModerationStatus.OK,
            )
            .select_related("author")
            .order_by("-created_at")[:100]
        )
        ctx["show_reviews_work"] = show_work
        return ctx


class ClientReviewCreateView(CabinetSectionMixin, LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = "users/cabinet/review_form.html"
    cabinet_section = "reviews"

    def dispatch(self, request, *args, **kwargs):
        self._booking = get_object_or_404(
            Booking.objects.filter(client=request.user),
            pk=kwargs["booking_pk"],
        )
        if self._booking.status != BookingStatus.COMPLETED:
            raise Http404
        if Review.objects.filter(booking=self._booking).exists() and request.method == "GET":
            messages.info(request, "Отзыв по этой записи уже оставлен.")
            return redirect("cabinet:bookings")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.booking = self._booking
        try:
            with transaction.atomic():
                self.object = form.save()
        except IntegrityError:
            messages.error(
                self.request,
                "Отзыв по этой записи уже добавлен.",
            )
            return self.form_invalid(form)

        rid = self.object.pk

        def _notify_sto() -> None:
            from apps.reviews.mail import mail_sto_new_review

            try:
                rev = Review.objects.select_related("booking", "booking__station").get(pk=rid)
                mail_sto_new_review(rev)
            except Exception:
                logger.exception("mail_sto_new_review failed review_id=%s", rid)

        transaction.on_commit(_notify_sto)
        messages.success(self.request, "Спасибо, отзыв сохранён.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("cabinet:bookings")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["booking"] = self._booking
        return ctx


class ClientReviewUpdateView(CabinetSectionMixin, LoginRequiredMixin, UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = "users/cabinet/review_edit.html"
    pk_url_kwarg = "pk"
    cabinet_section = "reviews"

    def get_queryset(self):
        return Review.objects.filter(booking__client=self.request.user)

    def _redirect_if_locked(self):
        self.object = self.get_object()
        if not self.object.is_editable_by_client():
            messages.error(
                self.request,
                f"Редактирование доступно только в течение {REVIEW_CLIENT_EDIT_HOURS} ч. после публикации.",
            )
            return redirect("cabinet:reviews")
        return None

    def get(self, request, *args, **kwargs):
        redir = self._redirect_if_locked()
        return redir if redir is not None else super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        redir = self._redirect_if_locked()
        return redir if redir is not None else super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Отзыв обновлён.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("cabinet:reviews")


class ClientSupportListView(CabinetSectionMixin, LoginRequiredMixin, ListView):
    """Список обращений в поддержку и форма нового тикета."""

    model = SupportTicket
    template_name = "users/cabinet/support_list.html"
    context_object_name = "tickets"
    cabinet_section = "support"

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).order_by("-updated_at", "-pk")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["support_body_min"] = int(getattr(settings, "SUPPORT_TICKET_BODY_MIN_LENGTH", 10))
        ctx["support_ticket_unread_ids"] = set(
            support_unread_tickets_for_user_qs(self.request.user).values_list("pk", flat=True)
        )
        return ctx


class ClientSupportDetailView(CabinetSectionMixin, LoginRequiredMixin, DetailView):
    model = SupportTicket
    template_name = "users/cabinet/support_detail.html"
    context_object_name = "ticket"
    cabinet_section = "support"

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        mark_ticket_read_by_user(self.object.pk, user_id=request.user.pk)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        t = ctx["ticket"]
        ctx["messages_list"] = list(
            t.messages.select_related("author").order_by("created_at", "pk")
        )
        return ctx


@login_required
@require_POST
def client_support_create(request):
    body = (request.POST.get("body") or "").strip()
    subject = (request.POST.get("subject") or "").strip()[:200]
    try:
        ticket = create_ticket_with_initial_message(request.user, body, subject=subject)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("cabinet:support")
    messages.success(request, "Обращение отправлено. Мы ответим в этой переписке.")
    return redirect("cabinet:support_detail", pk=ticket.pk)
