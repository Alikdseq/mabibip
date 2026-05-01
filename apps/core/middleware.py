"""HTTP middleware."""

from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse

from .visitor_city import ensure_visitor_city_in_session


class VisitorCityMiddleware:
    """Подставляет город в сессию до рендера (сценарий: шапка, каталог, главная)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ensure_visitor_city_in_session(request)
        return self.get_response(request)
