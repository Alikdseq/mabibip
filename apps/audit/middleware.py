from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from .utils import audit_log


def _client_ip(request: HttpRequest) -> str | None:
    """
    Best-effort IP extraction.
    In Docker behind proxy, X-Forwarded-For may be present; we take the first hop.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
        return ip or None
    return request.META.get("REMOTE_ADDR")


class AdminAuditMiddleware:
    """
    Lightweight audit for admin area requests.

    Не пишет логи для каждого запроса целиком (чтобы не засорять БД),
    а фиксирует:
    - вход в админку (GET /secure-admin/ -> 302/200),
    - ошибки/запреты (4xx/5xx) в админке,
    - POST/PUT/PATCH/DELETE запросы в админке (как "операция").
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = timezone.now()
        response = self.get_response(request)

        path = request.path or ""
        if not path.startswith("/secure-admin/"):
            return response

        method = (request.method or "").upper()
        status = getattr(response, "status_code", None)

        should_log = False
        event_type = ""
        action = ""

        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            should_log = True
            event_type = "admin.request"
            action = method.lower()
        elif status and status >= 500:
            should_log = True
            event_type = "admin.error"
            action = "server_error"
        elif status and status in {401, 403, 404}:
            should_log = True
            event_type = "admin.access"
            action = "denied"

        if should_log:
            audit_log(
                request=request,
                event_type=event_type,
                action=action,
                object_label="Admin request",
                payload={
                    "duration_ms": int((timezone.now() - started).total_seconds() * 1000),
                },
                status_code=status,
            )

        return response

