from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from rest_framework.response import Response


def onboarding_needed(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    contact_phone = (getattr(user, "contact_phone", "") or "").strip()
    return not contact_phone


def _complete_profile_url(*, next_url: str | None) -> str:
    base = reverse("cabinet:profile")
    if not next_url:
        return base
    return f"{base}?{urlencode({'next': next_url})}"


def redirect_to_complete_profile(request: HttpRequest) -> HttpResponse:
    next_url = request.get_full_path()
    messages.info(request, "Заполните телефон для связи, чтобы продолжить.")
    return redirect(_complete_profile_url(next_url=next_url))


def require_completed_profile(view_func):
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if onboarding_needed(request.user):
            return redirect_to_complete_profile(request)
        return view_func(request, *args, **kwargs)

    return _wrapped


class CompletedProfileRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if onboarding_needed(request.user):
            return redirect_to_complete_profile(request)
        return super().dispatch(request, *args, **kwargs)


def ensure_completed_profile_api(request) -> Response | None:
    """
    Для JS/API: вместо редиректа отдаём JSON с redirect_url.
    """
    if not onboarding_needed(request.user):
        return None
    return Response(
        {
            "ok": False,
            "error": "Заполните телефон для связи, чтобы продолжить.",
            "redirect_url": _complete_profile_url(next_url=getattr(request, "path", "") or "/"),
        },
        status=403,
    )

