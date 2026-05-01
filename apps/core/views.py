"""Общие представления (не привязаны к домену станций)."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .seo import _absolute_base_for_request, robots_txt_body
from .visitor_city import SESSION_KEY, list_allowed_city_labels


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    base = _absolute_base_for_request(request)
    sitemap_abs = f"{base}{reverse('seo_sitemap')}"
    body = robots_txt_body(sitemap_absolute_url=sitemap_abs)
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_POST
def set_visitor_city(request: HttpRequest) -> HttpResponse:
    label = (request.POST.get("city_label") or "").strip()
    allowed = list_allowed_city_labels()
    if not allowed:
        messages.warning(request, "Список городов пока не настроен.")
        return redirect("home")
    if label not in allowed:
        messages.error(request, "Выберите город из списка.")
        return redirect(request.META.get("HTTP_REFERER") or "/")
    request.session[SESSION_KEY] = label
    messages.success(request, f"Город: {label}")
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(request.META.get("HTTP_REFERER") or "/")
