"""Ограничение действий для пользователей с неподтверждённым email (ТЗ п. 9.4)."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect


def is_business_approved(user) -> bool:
    """
    True, если пользователь — бизнес-роль и его заявка одобрена администратором.

    Для таких аккаунтов требования подтверждения email снимаются.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if not bool(getattr(user, "is_sto_owner", False)):
        return False
    if getattr(user, "sto_moderation_status", "") != "approved":
        return False
    role = getattr(user, "business_role", "")
    return role in {"master", "autoservice", "autoshop"}


def email_verification_needed(user) -> bool:
    """True, если у пользователя указан email, но он ещё не подтверждён по ссылке."""
    if not getattr(user, "is_authenticated", False):
        return False
    if is_business_approved(user):
        return False
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        return False
    return not bool(getattr(user, "email_verified", True))


def contacts_email_verification_needed(user) -> bool:
    """
    True, если для просмотра контактов требуется подтверждённый email.

    Водители: без email или без подтверждения email — блок.
    Одобренный бизнес: блок снимается даже без подтверждения email.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if is_business_approved(user):
        return False
    from .registration_flags import registration_lite_enabled

    if registration_lite_enabled() and not (getattr(user, "email", None) or "").strip():
        return False
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        return True
    return not bool(getattr(user, "email_verified", True))


def redirect_to_email_notice(request):
    messages.warning(
        request,
        "Подтвердите адрес электронной почты — без этого действие недоступно. "
        "Проверьте входящие или запросите письмо повторно.",
    )
    return redirect("users:email_verification_notice")


class EmailVerificationRequiredMixin(AccessMixin):
    """Для CBV: редирект, если email указан, но не подтверждён."""

    def dispatch(self, request, *args, **kwargs):
        if email_verification_needed(request.user):
            return redirect_to_email_notice(request)
        return super().dispatch(request, *args, **kwargs)


def require_verified_email(view_func):
    """Для функций с @login_required: проверка после авторизации."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if email_verification_needed(request.user):
            return redirect_to_email_notice(request)
        return view_func(request, *args, **kwargs)

    return _wrapped
