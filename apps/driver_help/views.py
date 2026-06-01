# -*- coding: utf-8 -*-

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.driver_help.forms import HelpRequestForm
from apps.driver_help.models import DriverHelpRequest, HelpRequestStatus
from apps.driver_help.services import active_help_count, create_help_request, help_to_payload, resolve_help_request


def _enabled() -> bool:
    return bool(getattr(settings, "DRIVER_HELP_ENABLED", True))


@require_GET
def help_feed(request: HttpRequest) -> HttpResponse:
    if not _enabled():
        raise Http404
    active = list(
        DriverHelpRequest.objects.filter(status=HelpRequestStatus.ACTIVE)
        .select_related("author")
        .order_by("-created_at")[:100]
    )
    ctx = {
        "help_requests": active,
        "help_active_count": len(active),
        "help_form": HelpRequestForm(),
        "seo_og_title": "Нужна помощь на дороге — МаБибип",
        "seo_meta_description": "Срочная помощь водителям рядом: застряли, не заводится, нужен выезд. Оставьте сообщение или откликнитесь — МаБибип.",
    }
    if request.headers.get("HX-Request"):
        return render(request, "driver_help/partials/feed_list.html", ctx)
    return render(request, "driver_help/feed.html", ctx)


@login_required
@require_POST
def help_create(request: HttpRequest) -> HttpResponse:
    if not _enabled():
        raise Http404
    form = HelpRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте текст обращения.")
        return redirect("driver_help:feed")
    try:
        create_help_request(author=request.user, message=form.cleaned_data["message"])
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("driver_help:feed")
    messages.success(request, "Сообщение опубликовано. Вам могут позвонить.")
    return redirect("driver_help:feed")


@login_required
@require_POST
def help_resolve(request: HttpRequest, pk: int) -> HttpResponse:
    if not _enabled():
        raise Http404
    req = get_object_or_404(
        DriverHelpRequest.objects.select_related("author"),
        pk=pk,
        status=HelpRequestStatus.ACTIVE,
    )
    if req.author_id == request.user.pk:
        messages.error(request, "Нельзя откликнуться на своё обращение.")
        return redirect("driver_help:feed")
    try:
        phone = resolve_help_request(req=req, resolver=request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("driver_help:feed")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "phone": phone, "id": pk})
    messages.success(request, f"Телефон: {phone}")
    return redirect("driver_help:feed")


@require_GET
def help_active_count_api(request: HttpRequest) -> JsonResponse:
    if not _enabled():
        return JsonResponse({"count": 0})
    return JsonResponse({"count": active_help_count()})
