from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.legal.models import REGISTRATION_REQUIRED_KEYS, get_current_version
from apps.legal.services import record_user_consents
from apps.stations.models import District, ServiceStation
from apps.core.city_expansion import record_business_city

from .onboarding_forms import OAuthOnboardingForm
from .profile_completion import registration_moderation_enabled
from .sto_moderation_mail import mail_admins_sto_registration_pending

User = get_user_model()


def _executor_kind_display(raw: str) -> str:
    from apps.stations.constants import EXECUTOR_KIND_CHOICES

    return dict(EXECUTOR_KIND_CHOICES).get(raw, raw)


def _apply_business_role_side_effects(
    *,
    user: User,
    role: str,
    business_name: str,
    city_label: str,
    autoshop_kind: str | None,
) -> None:
    if role == User.BusinessRole.DRIVER:
        return

    from apps.users.profile_completion import registration_moderation_enabled

    record_business_city(city_label)
    district = District.objects.filter(city_label=city_label).order_by("pk").first()

    if role == User.BusinessRole.INSTRUCTOR:
        from apps.driving_instructors.models import DrivingInstructorProfile

        DrivingInstructorProfile.objects.get_or_create(
            owner=user,
            defaults={
                "name": business_name,
                "city_label": city_label,
                "contact_phone": user.contact_phone or user.phone,
                "is_published": False,
            },
        )
        return

    user.is_sto_owner = True
    user.sto_moderation_status = (
        User.StoModerationStatus.PENDING
        if registration_moderation_enabled()
        else User.StoModerationStatus.APPROVED
    )
    user.save(update_fields=["is_sto_owner", "sto_moderation_status"])

    if role in (User.BusinessRole.MASTER, User.BusinessRole.AUTOSERVICE):
        from apps.stations.constants import EXECUTOR_KIND_PRIVATE, EXECUTOR_KIND_STO

        executor_kind = EXECUTOR_KIND_PRIVATE if role == User.BusinessRole.MASTER else EXECUTOR_KIND_STO
        ServiceStation.objects.create(
            owner=user,
            name=business_name,
            address=f"{city_label}, адрес уточняется после модерации",
            executor_kind=executor_kind,
            is_active=False,
            district=district,
        )
        return

    from apps.classifieds.models import AutoShopProfile

    AutoShopProfile.objects.create(
        owner=user,
        name=business_name,
        city_label=city_label,
        contact_phone=user.contact_phone,
        kind=autoshop_kind or AutoShopProfile.Kind.SHOP,
    )


@login_required
def complete_profile(request: HttpRequest) -> HttpResponse:
    """
    Онбординг после OAuth: роль + контактный телефон.

    Сайт доступен, но ключевые действия будут мягко блокироваться,
    пока пользователь не заполнит эти данные.
    """
    u: User = request.user
    if u.contact_phone and u.business_role_chosen:
        return redirect(request.GET.get("next") or reverse("home"))

    if request.method == "POST":
        form = OAuthOnboardingForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            role = cd["role"]
            with transaction.atomic():
                u.contact_phone = cd["contact_phone"]
                u.business_role = role
                u.business_role_chosen = True
                u.save(update_fields=["contact_phone", "business_role", "business_role_chosen"])

                _apply_business_role_side_effects(
                    user=u,
                    role=role,
                    business_name=(cd.get("business_name") or "").strip(),
                    city_label=(cd.get("city_label") or "").strip(),
                    autoshop_kind=(cd.get("autoshop_kind") or None),
                )

                versions = [get_current_version(k) for k in REGISTRATION_REQUIRED_KEYS]
                record_user_consents(u, versions, request)

            if role == User.BusinessRole.DRIVER:
                messages.success(request, "Профиль заполнен. Добро пожаловать!")
                return redirect(request.GET.get("next") or reverse("home"))
            if role == User.BusinessRole.INSTRUCTOR:
                messages.success(
                    request,
                    "Профиль заполнен. Заполните карточку автоинструктора.",
                )
                return redirect("instructor_owner:profile_edit")
            if role == User.BusinessRole.AUTOSHOP:
                if registration_moderation_enabled():
                    messages.success(
                        request,
                        "Профиль заполнен. Добро пожаловать в кабинет автомагазина!",
                    )
                    return redirect("shop_owner:dashboard")
                from .views import _redirect_after_business_registration

                return _redirect_after_business_registration(request, u, role=role)

            if registration_moderation_enabled():
                from apps.stations.constants import EXECUTOR_KIND_PRIVATE, EXECUTOR_KIND_STO

                mail_admins_sto_registration_pending(
                    user=u,
                    station_name=(cd.get("business_name") or "").strip(),
                    city_label=(cd.get("city_label") or "").strip(),
                    executor_kind_display=_executor_kind_display(
                        EXECUTOR_KIND_PRIVATE if role == User.BusinessRole.MASTER else EXECUTOR_KIND_STO
                    ),
                )
                messages.success(
                    request,
                    "Заявка отправлена. После проверки модератором вы получите доступ к кабинету бизнеса.",
                )
                return redirect("sto_owner:pending_moderation")
            from .views import _redirect_after_business_registration

            return _redirect_after_business_registration(request, u, role=role)
    else:
        form = OAuthOnboardingForm(
            initial={
                "role": u.business_role or User.BusinessRole.DRIVER,
                "contact_phone": u.contact_phone or "",
            }
        )

    return render(request, "users/complete_profile.html", {"form": form})

