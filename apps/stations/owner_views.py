"""Личный кабинет владельца СТО (фаза 5)."""

import logging
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import FormView, ListView, TemplateView, View

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.services import (
    apply_owner_booking_transition,
    owner_propose_booking_reschedule,
)
from apps.reviews.models import ModerationStatus, Review, ReviewComplaint, ReviewReply
from apps.reviews.owner_forms import OwnerReviewComplaintForm, OwnerReviewReplyForm
from apps.stations.models import ServiceCategory, ServiceSection, ServiceStation, WorkBay
from apps.stations.owner_forms import (
    StationBrandsForm,
    StationOwnerProfileForm,
    StationServiceOfferFormSet,
    StationMasterCreateForm,
    StationMasterFullCreateForm,
    StationMasterQuickEditForm,
    TimeSlotCreateForm,
    TimeSlotQuickTodayForm,
    WorkBayCreateForm,
)
from apps.stations.slot_calendar import build_week_calendar_context, monday_of_week
from apps.stations.sto_stats import monthly_booking_series_for_owner, subscription_rows_for_owner
from apps.stations.visibility import station_is_visible
from apps.users.models import User

logger = logging.getLogger(__name__)

BOOKINGS_ALL_PAGE_SIZE = 5


def _bookings_all_upcoming_qs(user):
    """
    Ожидающие подтверждения (любая дата) + подтверждённые на будущее (слот ещё не начался по локальному времени).
    Сортировка: ближайшая дата/время первой.
    """
    now = timezone.now()
    today = timezone.localdate()
    cur_t = timezone.localtime(now).time()
    return (
        Booking.objects.filter(station__owner=user)
        .filter(
            Q(status=BookingStatus.PENDING)
            | (
                Q(status=BookingStatus.CONFIRMED)
                & (Q(slot__date__gt=today) | Q(slot__date=today, slot__start_time__gte=cur_t))
            )
        )
        .select_related("slot", "slot__bay", "station", "client")
        .order_by("slot__date", "slot__start_time", "pk")
    )


def _sto_owner_approved(user) -> bool:
    if not user.is_authenticated or not getattr(user, "is_sto_owner", False):
        return False
    if getattr(user, "business_role", "") == User.BusinessRole.AUTOSHOP:
        return False
    return user.sto_moderation_status == User.StoModerationStatus.APPROVED


def _owner_stations(user):
    return ServiceStation.objects.filter(owner=user)


def _owner_billing_blocks_dashboard(user) -> bool:
    """Все станции владельца скрыты из каталога по подписке — показываем заглушку (шаг 5.1.8)."""
    stations = _owner_stations(user)
    if not stations.exists():
        return True
    today = timezone.localdate()
    return all(not station_is_visible(s, today) for s in stations)


def _attach_prior_completed_visits(bookings_list: list, owner_user) -> None:
    """Число завершённых визитов этого клиента на этой станции (без текущей записи)."""
    if not bookings_list:
        return
    pairs = {(b.client_id, b.station_id) for b in bookings_list}
    q = Q()
    for cid, sid in pairs:
        q |= Q(client_id=cid, station_id=sid)
    rows = Booking.objects.filter(
        q,
        station__owner=owner_user,
        status=BookingStatus.COMPLETED,
    ).values_list("client_id", "station_id", "pk")
    by_pair = defaultdict(set)
    for cid, sid, pk in rows:
        by_pair[(cid, sid)].add(pk)
    for b in bookings_list:
        pks = by_pair.get((b.client_id, b.station_id), set())
        b.prior_completed_visits = len(pks - {b.pk})


def _month_stats_booking_count(user) -> int:
    """
    Статистика месяца: брони по станциям владельца, **без отменённых**
    (зафиксировано в тесте 5.1.T3).
    """
    now = timezone.localdate()
    return (
        Booking.objects.filter(
            station__owner=user,
            created_at__year=now.year,
            created_at__month=now.month,
        )
        .exclude(status=BookingStatus.CANCELED)
        .count()
    )


class StoOwnerRequiredMixin(UserPassesTestMixin):
    login_url = reverse_lazy("users:login")

    def dispatch(self, request, *args, **kwargs):
        u = request.user
        from apps.users.onboarding_access import onboarding_needed, redirect_to_complete_profile

        if onboarding_needed(u):
            return redirect_to_complete_profile(request)
        if u.is_authenticated and getattr(u, "is_sto_owner", False) and getattr(u, "business_role", "") == User.BusinessRole.AUTOSHOP:
            return redirect("shop_owner:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        u = self.request.user
        return _sto_owner_approved(u)


class StoModerationPendingView(UserPassesTestMixin, TemplateView):
    """Экран ожидания решения администратора (премодерация заявки СТО)."""

    template_name = "sto_owner/pending_moderation.html"
    login_url = reverse_lazy("users:login")

    def dispatch(self, request, *args, **kwargs):
        from apps.users.onboarding_access import onboarding_needed, redirect_to_complete_profile

        if onboarding_needed(request.user):
            return redirect_to_complete_profile(request)
        if request.user.is_authenticated and getattr(request.user, "is_sto_owner", False):
            if getattr(request.user, "business_role", "") == User.BusinessRole.AUTOSHOP:
                return redirect("shop_owner:dashboard")
            st = request.user.sto_moderation_status
            if st == User.StoModerationStatus.APPROVED:
                return redirect("sto_owner:dashboard")
            if st == User.StoModerationStatus.REJECTED:
                return redirect("sto_owner:moderation_rejected")
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        u = self.request.user
        return (
            u.is_authenticated
            and u.is_sto_owner
            and u.business_role != User.BusinessRole.AUTOSHOP
            and u.sto_moderation_status == User.StoModerationStatus.PENDING
        )


class StoModerationRejectedView(UserPassesTestMixin, TemplateView):
    """Заявка отклонена администратором."""

    template_name = "sto_owner/moderation_rejected.html"
    login_url = reverse_lazy("users:login")

    def dispatch(self, request, *args, **kwargs):
        from apps.users.onboarding_access import onboarding_needed, redirect_to_complete_profile

        if onboarding_needed(request.user):
            return redirect_to_complete_profile(request)
        if request.user.is_authenticated and getattr(request.user, "is_sto_owner", False):
            if getattr(request.user, "business_role", "") == User.BusinessRole.AUTOSHOP:
                return redirect("shop_owner:dashboard")
            st = request.user.sto_moderation_status
            if st == User.StoModerationStatus.APPROVED:
                return redirect("sto_owner:dashboard")
            if st == User.StoModerationStatus.PENDING:
                return redirect("sto_owner:pending_moderation")
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        u = self.request.user
        return (
            u.is_authenticated
            and u.is_sto_owner
            and u.business_role != User.BusinessRole.AUTOSHOP
            and u.sto_moderation_status == User.StoModerationStatus.REJECTED
        )


class StoOwnerDashboardView(StoOwnerRequiredMixin, TemplateView):
    template_name = "sto_owner/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            if self.request.session.pop("dup_slot_msg", ""):
                ctx["dup_slot_msg"] = True
        except Exception:
            ctx["dup_slot_msg"] = False
        ctx["catalog_subscription_relaxed"] = getattr(settings, "CATALOG_BYPASS_SUBSCRIPTION", False)
        user = self.request.user
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        ctx["subscription_rows"] = subscription_rows_for_owner(user)
        ctx["monthly_booking_stats"] = monthly_booking_series_for_owner(user)
        ctx["slot_calendar_url"] = reverse_lazy("sto_owner:slot_calendar")

        if _owner_billing_blocks_dashboard(user):
            ctx["billing_blocked"] = True
            ctx["month_stats_count"] = 0
            ctx["bookings_today"] = Booking.objects.none()
            ctx["bookings_tomorrow"] = Booking.objects.none()
            ctx["bookings_all"] = []
            ctx["bookings_all_total"] = 0
            ctx["bookings_all_has_more"] = False
            ctx["bookings_all_remaining"] = 0
            ctx["slot_calendar_url"] = reverse_lazy("sto_owner:slot_calendar")
            ctx["bays_url"] = reverse_lazy("sto_owner:bays")
            return ctx

        ctx["billing_blocked"] = False
        base = (
            Booking.objects.filter(station__owner=user)
            .select_related("slot", "slot__bay", "station", "client")
            .order_by("slot__start_time", "pk")
        )
        bookings_today = list(base.filter(slot__date=today))
        bookings_tomorrow = list(base.filter(slot__date=tomorrow))
        _attach_prior_completed_visits(bookings_today, user)
        _attach_prior_completed_visits(bookings_tomorrow, user)
        ctx["bookings_today"] = bookings_today
        ctx["bookings_tomorrow"] = bookings_tomorrow

        all_qs = _bookings_all_upcoming_qs(user)
        all_total = all_qs.count()
        bookings_all = list(all_qs[:BOOKINGS_ALL_PAGE_SIZE])
        _attach_prior_completed_visits(bookings_all, user)
        ctx["bookings_all"] = bookings_all
        ctx["bookings_all_total"] = all_total
        ctx["bookings_all_has_more"] = all_total > BOOKINGS_ALL_PAGE_SIZE
        ctx["bookings_all_remaining"] = max(0, all_total - BOOKINGS_ALL_PAGE_SIZE)

        ctx["month_stats_count"] = _month_stats_booking_count(user)
        ctx["slot_add_url"] = reverse_lazy("sto_owner:slot_add")
        ctx["stations_manage_url"] = reverse_lazy("sto_owner:stations")
        ctx["reviews_url"] = reverse_lazy("sto_owner:reviews")
        ctx["bays_url"] = reverse_lazy("sto_owner:bays")
        return ctx


class BillingRequiredView(StoOwnerRequiredMixin, TemplateView):
    template_name = "sto_owner/billing_required.html"


@login_required(login_url=reverse_lazy("users:login"))
@require_GET
def dashboard_bookings_all_more(request):
    """Подгрузка следующих записей для вкладки «Все записи» (HTMX)."""
    user = request.user
    if not _sto_owner_approved(user):
        raise Http404
    if _owner_billing_blocks_dashboard(user):
        raise Http404
    try:
        offset = int(request.GET.get("offset", "0"))
    except ValueError:
        offset = 0
    if offset < BOOKINGS_ALL_PAGE_SIZE:
        offset = BOOKINGS_ALL_PAGE_SIZE
    qs = _bookings_all_upcoming_qs(user)
    total = qs.count()
    if offset >= total:
        raise Http404
    batch = list(qs[offset : offset + BOOKINGS_ALL_PAGE_SIZE])
    _attach_prior_completed_visits(batch, user)
    next_offset = offset + len(batch)
    return render(
        request,
        "sto_owner/dashboard_bookings_all_more.html",
        {
            "bookings": batch,
            "has_more": next_offset < total,
            "next_offset": next_offset,
            "remaining": max(0, total - next_offset),
        },
    )


@login_required(login_url=reverse_lazy("users:login"))
@require_POST
def dashboard_quick_slot_today(request):
    """Быстрое добавление окна записи на сегодня с дашборда (модальная форма)."""
    user = request.user
    if not _sto_owner_approved(user):
        raise Http404
    if _owner_billing_blocks_dashboard(user):
        messages.warning(request, "Добавление окон недоступно до продления подписки.")
        return redirect("sto_owner:dashboard")
    today = timezone.localdate()
    post = request.POST.copy()
    post["date"] = today.isoformat()
    post["is_available"] = "on"
    form = TimeSlotQuickTodayForm(post, owner=user, today=today)
    if form.is_valid():
        bay = form.cleaned_data.get("bay")
        st = form.cleaned_data.get("start_time")
        if bay and st and TimeSlot.objects.filter(bay=bay, date=today, start_time=st).exists():
            messages.error(
                request,
                "На этом посту уже есть окно с таким временем начала на выбранную дату.",
            )
            request.session["dup_slot_msg"] = "1"
            return redirect("sto_owner:dashboard")
        try:
            form.save()
        except IntegrityError:
            messages.error(
                request,
                "На этом посту уже есть окно с таким временем начала на выбранную дату.",
            )
            request.session["dup_slot_msg"] = "1"
        else:
            messages.success(request, "Окно на сегодня добавлено.")
    else:
        err = None
        for errs in form.errors.values():
            for line in errs:
                err = str(line)
                break
            if err:
                break
        msg = err or "Не удалось добавить окно — проверьте поля."
        messages.error(request, msg)
        if "окно" in (msg or "").casefold():
            request.session["dup_slot_msg"] = "1"
    return redirect("sto_owner:dashboard")


class TimeSlotCreateView(StoOwnerRequiredMixin, FormView):
    form_class = TimeSlotCreateForm
    template_name = "sto_owner/slot_form.html"

    def dispatch(self, request, *args, **kwargs):
        if _owner_billing_blocks_dashboard(request.user):
            messages.warning(request, "Добавление окон недоступно до продления подписки.")
            return redirect("sto_owner:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["owner"] = self.request.user
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        ctx["owner_has_bays"] = WorkBay.objects.filter(station__owner=user).exists()
        if ctx["owner_has_bays"]:
            ctx["quick_slot_form"] = TimeSlotQuickTodayForm(owner=user, today=today)
        return ctx

    def form_valid(self, form):
        slot = form.save()
        messages.success(self.request, "Окно записи добавлено.")
        week_mon = monday_of_week(slot.date)
        url = (
            reverse("sto_owner:slot_calendar")
            + f"?station={slot.bay.station.slug}&week={week_mon.isoformat()}"
        )
        return HttpResponseRedirect(url)


class OwnerStationsView(StoOwnerRequiredMixin, TemplateView):
    template_name = "sto_owner/stations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stations"] = (
            ServiceStation.objects.filter(owner=self.request.user)
            .prefetch_related("car_brands")
            .order_by("name", "pk")
        )
        ctx["bays_url"] = reverse_lazy("sto_owner:bays")
        return ctx


class OwnerMastersView(StoOwnerRequiredMixin, TemplateView):
    template_name = "sto_owner/masters.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        stations = list(ServiceStation.objects.filter(owner=user, executor_kind="sto").order_by("name", "pk"))
        masters = list(
            ServiceStation.objects.filter(owner=user, executor_kind="private", parent_station__isnull=False)
            .select_related("parent_station")
            .order_by("parent_station__name", "name", "pk")
        )
        ctx["stations"] = stations
        ctx["masters"] = masters
        ctx["master_add_url"] = reverse("sto_owner:master_add")
        ctx["master_update_url_name"] = "sto_owner:master_update"
        ctx["master_inherit_url_name"] = "sto_owner:master_inherit"
        ctx["master_rows"] = [{"master": m, "form": StationMasterQuickEditForm(instance=m)} for m in masters]
        return ctx


class MasterCreateView(StoOwnerRequiredMixin, FormView):
    form_class = StationMasterFullCreateForm
    template_name = "sto_owner/master_form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["files"] = self.request.FILES
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["stations"] = list(ServiceStation.objects.filter(owner=user, executor_kind="sto").order_by("name", "pk"))
        return ctx

    def form_valid(self, form):
        user = self.request.user
        try:
            parent_id = int(self.request.POST.get("parent_station_id") or "0")
        except ValueError:
            parent_id = 0
        parent = ServiceStation.objects.filter(owner=user, executor_kind="sto", pk=parent_id).first()
        if not parent:
            messages.error(self.request, "Выберите автосервис, к которому относится мастер.")
            return self.form_invalid(form)

        with transaction.atomic():
            m = form.save(commit=False)
            m.owner = user
            m.parent_station = parent
            m.executor_kind = "private"
            # наследуем базовые настройки от сервиса
            m.address = parent.address
            m.district = parent.district
            m.subscription_plan = parent.subscription_plan
            m.subscription_paid_until = parent.subscription_paid_until
            m.is_active = parent.is_active
            m.address_public_mode = parent.address_public_mode
            m.save()
            form.save_m2m()

        messages.success(self.request, "Мастер добавлен.")
        return redirect("sto_owner:masters")


@user_passes_test(_sto_owner_approved)
@require_POST
def master_delete(request, pk):
    m = get_object_or_404(
        ServiceStation.objects.filter(owner=request.user, executor_kind="private", parent_station__isnull=False),
        pk=pk,
    )
    # Не даём удалить, если есть записи
    slot_ids = list(TimeSlot.objects.filter(bay__station=m).values_list("pk", flat=True))
    if slot_ids and Booking.objects.filter(slot_id__in=slot_ids).exclude(status=BookingStatus.CANCELED).exists():
        messages.error(request, "Нельзя удалить мастера: есть активные записи. Сначала завершите/отмените заявки.")
        return redirect("sto_owner:masters")
    with transaction.atomic():
        TimeSlot.objects.filter(bay__station=m).delete()
        WorkBay.objects.filter(station=m).delete()
        m.delete()
    messages.success(request, "Мастер удалён.")
    return redirect("sto_owner:masters")


@user_passes_test(_sto_owner_approved)
@require_POST
def master_update(request, pk):
    m = get_object_or_404(
        ServiceStation.objects.filter(owner=request.user, executor_kind="private", parent_station__isnull=False),
        pk=pk,
    )
    form = StationMasterQuickEditForm(request.POST, request.FILES, instance=m)
    if not form.is_valid():
        messages.error(request, "Проверьте поля мастера (есть ошибки).")
        return redirect("sto_owner:masters")
    form.save()
    messages.success(request, "Данные мастера обновлены.")
    return redirect("sto_owner:masters")


@user_passes_test(_sto_owner_approved)
@require_POST
def master_inherit(request, pk):
    m = get_object_or_404(
        ServiceStation.objects.filter(owner=request.user, executor_kind="private", parent_station__isnull=False),
        pk=pk,
    )
    parent = m.parent_station
    if not parent:
        messages.error(request, "У мастера не указан автосервис-родитель.")
        return redirect("sto_owner:masters")

    # Наследуем только безопасные поля (без услуг), чтобы не перетирать настройки мастера.
    m.address = parent.address
    m.district = parent.district
    m.address_public_mode = parent.address_public_mode
    m.contact_phone = parent.contact_phone
    m.whatsapp_phone = parent.whatsapp_phone
    m.telegram_username = parent.telegram_username
    m.website = parent.website
    m.vk_url = parent.vk_url
    m.instagram_url = parent.instagram_url
    m.work_schedule_text = parent.work_schedule_text
    m.is_open_24_7 = parent.is_open_24_7
    m.has_parking = parent.has_parking
    m.car_brands_all = parent.car_brands_all
    m.save(update_fields=[
        "address",
        "district",
        "address_public_mode",
        "contact_phone",
        "whatsapp_phone",
        "telegram_username",
        "website",
        "vk_url",
        "instagram_url",
        "work_schedule_text",
        "is_open_24_7",
        "has_parking",
        "car_brands_all",
    ])
    m.car_brands.set(parent.car_brands.all())

    messages.success(request, "Мастер унаследовал адрес/контакты/марки от сервиса.")
    return redirect("sto_owner:masters")


class OwnerBaysView(StoOwnerRequiredMixin, TemplateView):
    template_name = "sto_owner/bays.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bays_qs = WorkBay.objects.annotate(slot_count=Count("slots")).order_by(
            "name", "pk"
        )
        stations = (
            ServiceStation.objects.filter(owner=self.request.user)
            .prefetch_related(Prefetch("bays", queryset=bays_qs))
            .order_by("name", "pk")
        )
        ctx["stations"] = stations
        ctx["bay_add_url"] = reverse_lazy("sto_owner:bay_add")
        return ctx


class WorkBayCreateView(StoOwnerRequiredMixin, FormView):
    form_class = WorkBayCreateForm
    template_name = "sto_owner/bay_form.html"
    success_url = reverse_lazy("sto_owner:bays")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["owner"] = self.request.user
        return kw

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Пост добавлен.")
        return super().form_valid(form)


class StationBrandsUpdateView(StoOwnerRequiredMixin, FormView):
    form_class = StationBrandsForm
    template_name = "sto_owner/station_brands_form.html"
    success_url = reverse_lazy("sto_owner:stations")

    def dispatch(self, request, *args, **kwargs):
        self._station = get_object_or_404(
            ServiceStation.objects.filter(owner=request.user),
            slug=kwargs.get("slug"),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["instance"] = self._station
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["station"] = self._station
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Марки обновлены. Фильтр в каталоге учитывает изменения сразу.")
        return super().form_valid(form)


class StationProfileEditView(StoOwnerRequiredMixin, View):
    """Карточка СТО / мастера: описание, контакты, категории, марки, прайс «от … ₽»."""

    template_name = "sto_owner/station_profile_form.html"

    def get_station(self):
        return get_object_or_404(
            ServiceStation.objects.filter(owner=self.request.user),
            slug=self.kwargs["slug"],
        )

    def get(self, request, *args, **kwargs):
        station = self.get_station()
        form = StationOwnerProfileForm(instance=station)
        formset = StationServiceOfferFormSet(instance=station)
        sections = list(ServiceSection.objects.order_by("sort_order", "name"))
        cats = list(ServiceCategory.objects.only("pk", "section_id").order_by("pk"))
        return render(
            request,
            self.template_name,
            {
                "station": station,
                "form": form,
                "formset": formset,
                "service_sections": sections,
                "category_section_map": {str(c.pk): (str(c.section_id) if c.section_id else "") for c in cats},
                "section_categories_map": {
                    str(s.pk): [str(c.pk) for c in cats if c.section_id == s.pk] for s in sections
                },
            },
        )

    def post(self, request, *args, **kwargs):
        station = self.get_station()
        form = StationOwnerProfileForm(request.POST, request.FILES, instance=station)
        formset = StationServiceOfferFormSet(request.POST, instance=station)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
            except IntegrityError:
                messages.error(
                    request,
                    "Не удалось сохранить прайс: для одной категории услуги уже есть строка. "
                    "Обновите страницу и убедитесь, что у каждой категории не больше одной строки.",
                )
                return render(
                    request,
                    self.template_name,
                    {"station": station, "form": form, "formset": formset},
                )
            from apps.users.profile_completion import maybe_activate_station_after_profile_save

            maybe_activate_station_after_profile_save(station)
            messages.success(request, "Профиль и прайс сохранены.")
            return redirect("sto_owner:station_profile", slug=station.slug)
        sections = list(ServiceSection.objects.order_by("sort_order", "name"))
        cats = list(ServiceCategory.objects.only("pk", "section_id").order_by("pk"))
        return render(
            request,
            self.template_name,
            {
                "station": station,
                "form": form,
                "formset": formset,
                "service_sections": sections,
                "category_section_map": {str(c.pk): (str(c.section_id) if c.section_id else "") for c in cats},
                "section_categories_map": {
                    str(s.pk): [str(c.pk) for c in cats if c.section_id == s.pk] for s in sections
                },
            },
        )


@user_passes_test(_sto_owner_approved)
@require_POST
def booking_confirm(request, pk):
    booking = get_object_or_404(Booking.objects.filter(station__owner=request.user), pk=pk)
    apply_owner_booking_transition(booking, BookingStatus.CONFIRMED, request.user)
    messages.success(request, "Запись подтверждена.")
    return redirect("sto_owner:dashboard")


@user_passes_test(_sto_owner_approved)
@require_POST
def booking_reject(request, pk):
    booking = get_object_or_404(Booking.objects.filter(station__owner=request.user), pk=pk)
    reason = (request.POST.get("cancel_reason") or "").strip()[:500]
    apply_owner_booking_transition(
        booking,
        BookingStatus.CANCELED,
        request.user,
        owner_cancel_reason=reason,
    )
    messages.info(request, "Заявка отклонена, слот снова доступен для записи.")
    return redirect("sto_owner:dashboard")


@user_passes_test(_sto_owner_approved)
@require_POST
def booking_start(request, pk):
    booking = get_object_or_404(Booking.objects.filter(station__owner=request.user), pk=pk)
    apply_owner_booking_transition(booking, BookingStatus.IN_PROGRESS, request.user)
    messages.success(request, "Работа по записи отмечена как начатая.")
    return redirect("sto_owner:dashboard")


@user_passes_test(_sto_owner_approved)
@require_POST
def booking_complete(request, pk):
    booking = get_object_or_404(Booking.objects.filter(station__owner=request.user), pk=pk)
    apply_owner_booking_transition(booking, BookingStatus.COMPLETED, request.user)
    messages.success(request, "Визит отмечен как завершённый.")
    return redirect("sto_owner:dashboard")


@user_passes_test(_sto_owner_approved)
@require_GET
def booking_reschedule_slots(request, pk):
    """JSON: свободные окна станции на день (для предложения переноса клиенту)."""
    from apps.bookings.slot_generation import run_generate_slots_for_station
    from apps.bookings.slot_rules import slot_is_bookable
    from apps.stations.constants import CATALOG_DAY_RANGE

    booking = get_object_or_404(
        Booking.objects.filter(station__owner=request.user).select_related("station"),
        pk=pk,
    )
    if booking.status != BookingStatus.PENDING:
        return JsonResponse({"slots": [], "error": "Только для новой заявки."}, status=400)
    raw = (request.GET.get("date") or "").strip()
    today = timezone.localdate()
    last = today + timedelta(days=CATALOG_DAY_RANGE - 1)
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return JsonResponse({"slots": [], "error": "Некорректная дата."}, status=400)
    if day < today or day > last:
        return JsonResponse({"slots": [], "error": "Дата вне доступного диапазона."}, status=400)

    run_generate_slots_for_station(station_id=booking.station_id, today=today, days_ahead=14)

    qs = (
        TimeSlot.objects.filter(
            bay__station_id=booking.station_id,
            date=day,
            is_available=True,
        )
        .select_related("bay")
        .order_by("start_time", "bay_id", "pk")
    )
    out = []
    for s in qs:
        if s.pk == booking.slot_id:
            continue
        if not slot_is_bookable(s, exclude_reschedule_for_booking_id=booking.pk):
            continue
        out.append(
            {
                "id": s.pk,
                "label": f"{s.start_time.strftime('%H:%M')}–{s.end_time.strftime('%H:%M')}, {s.bay.name}",
            }
        )
    return JsonResponse({"slots": out})


@user_passes_test(_sto_owner_approved)
@require_POST
def booking_propose_reschedule(request, pk):
    booking = get_object_or_404(Booking.objects.filter(station__owner=request.user), pk=pk)
    try:
        sid = int(request.POST.get("new_slot_id") or "0")
    except ValueError:
        messages.error(request, "Выберите окно из списка.")
        return redirect("sto_owner:dashboard")
    msg = (request.POST.get("owner_message") or "").strip()
    try:
        owner_propose_booking_reschedule(
            booking=booking,
            actor=request.user,
            new_slot_id=sid,
            owner_message=msg,
        )
    except ValueError as e:
        messages.error(request, str(e))
    except Http404:
        raise
    else:
        messages.success(request, "Предложение отправлено клиенту.")
    return redirect("sto_owner:dashboard")


@user_passes_test(_sto_owner_approved)
@require_POST
def bay_delete(request, pk):
    bay = get_object_or_404(WorkBay.objects.filter(station__owner=request.user), pk=pk)
    slot_ids = list(TimeSlot.objects.filter(bay=bay).values_list("pk", flat=True))
    if slot_ids and Booking.objects.filter(slot_id__in=slot_ids).exists():
        messages.error(
            request,
            "Нельзя удалить пост: к его слотам привязаны записи клиентов. "
            "Завершите или отмените заявки; при необходимости обратитесь к администратору.",
        )
        return redirect("sto_owner:bays")
    with transaction.atomic():
        TimeSlot.objects.filter(bay=bay).delete()
        bay.delete()
    messages.success(request, "Пост удалён.")
    return redirect("sto_owner:bays")


class OwnerReviewListView(StoOwnerRequiredMixin, ListView):
    """Отзывы по станциям владельца: ответ и жалоба (сценарий B2B)."""

    model = Review
    template_name = "sto_owner/review_list.html"
    context_object_name = "reviews"
    paginate_by = 20

    def get_queryset(self):
        return (
            Review.objects.filter(station__owner=self.request.user)
            .exclude(moderation_status=ModerationStatus.HIDDEN)
            .select_related("author", "station", "booking", "booking__client", "owner_reply")
            .order_by("-created_at")
        )


class OwnerReviewReplyView(StoOwnerRequiredMixin, FormView):
    form_class = OwnerReviewReplyForm
    template_name = "sto_owner/review_reply.html"
    success_url = reverse_lazy("sto_owner:reviews")

    def dispatch(self, request, *args, **kwargs):
        self.review = get_object_or_404(
            Review.objects.filter(station__owner=request.user).select_related(
                "station", "booking", "owner_reply"
            ),
            pk=kwargs["review_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        reply = getattr(self.review, "owner_reply", None)
        if reply:
            return {"text": reply.text}
        return {}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["review"] = self.review
        ctx["booking"] = self.review.booking
        ctx["station"] = self.review.station
        return ctx

    def form_valid(self, form):
        ReviewReply.objects.update_or_create(
            review=self.review,
            defaults={"text": form.cleaned_data["text"].strip()},
        )
        messages.success(self.request, "Ответ сохранён и показывается гостям на странице СТО.")
        return super().form_valid(form)


@user_passes_test(_sto_owner_approved)
@require_POST
def review_complaint(request, review_pk):
    review = get_object_or_404(
        Review.objects.filter(station__owner=request.user),
        pk=review_pk,
    )
    form = OwnerReviewComplaintForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Заполните форму жалобы.")
        return redirect("sto_owner:reviews")
    ReviewComplaint.objects.create(
        review=review,
        station=review.station,
        reason=form.cleaned_data["reason"].strip()[:300],
    )
    messages.success(request, "Жалоба отправлена модератору платформы.")
    return redirect("sto_owner:reviews")


class SlotCalendarView(StoOwnerRequiredMixin, TemplateView):
    """Недельный календарь слотов: свободно / запись / вручную закрыто."""

    template_name = "sto_owner/slot_calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        stations = list(ServiceStation.objects.filter(owner=user).order_by("name", "pk"))
        if not stations:
            ctx["no_stations"] = True
            return ctx

        slug = self.request.GET.get("station") or stations[0].slug
        station = get_object_or_404(ServiceStation.objects.filter(owner=user), slug=slug)

        week_raw = self.request.GET.get("week")
        if week_raw:
            try:
                anchor = date.fromisoformat(week_raw)
            except ValueError:
                anchor = timezone.localdate()
        else:
            anchor = timezone.localdate()

        # Автозаполняем слоты для станции на ближайшие ~2 недели,
        # чтобы календарь был "полным" без ручного добавления.
        try:
            from apps.bookings.slot_generation import run_generate_slots_for_station

            run_generate_slots_for_station(station_id=station.pk, today=timezone.localdate(), days_ahead=14)
        except Exception:
            # best-effort: календарь должен открываться даже если генерация упала
            logger.exception("slot auto-generation failed station_id=%s", station.pk)

        ctx.update(
            build_week_calendar_context(
                station=station,
                anchor_date=anchor,
                owner_stations=stations,
            )
        )
        ctx["no_stations"] = False
        ctx["today"] = timezone.localdate()
        return ctx


@user_passes_test(_sto_owner_approved)
@require_POST
def slot_toggle_block(request, pk):
    slot = get_object_or_404(
        TimeSlot.objects.filter(bay__station__owner=request.user).select_related("bay", "bay__station"),
        pk=pk,
    )
    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("note") or "").strip()[:200]

    if action == "block":
        if Booking.objects.filter(slot=slot).exclude(status=BookingStatus.CANCELED).exists():
            messages.error(
                request,
                "Нельзя закрыть слот: есть активная запись. Сначала отмените её в списке заказов.",
            )
        else:
            slot.is_available = False
            slot.manual_block_note = note
            slot.save(update_fields=["is_available", "manual_block_note"])
            messages.success(request, "Слот закрыт для новых записей.")
    elif action == "unblock":
        slot.is_available = True
        slot.manual_block_note = ""
        slot.save(update_fields=["is_available", "manual_block_note"])
        messages.success(request, "Слот снова доступен для записи.")
    else:
        messages.error(request, "Неизвестное действие.")

    params = {}
    w = (request.POST.get("week") or "").strip()
    st = (request.POST.get("station") or "").strip()
    if w:
        params["week"] = w
    if st:
        params["station"] = st
    target = reverse("sto_owner:slot_calendar")
    if params:
        target = f"{target}?{urlencode(params)}"
    return redirect(target)
