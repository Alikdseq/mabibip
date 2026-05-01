"""Сервисный слой: запись согласий без дублирования логики во views."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest

from .models import LegalDocumentVersion, UserConsent

if TYPE_CHECKING:
    from apps.users.models import User


def _client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _short_ua(request: HttpRequest) -> str:
    raw = (request.META.get("HTTP_USER_AGENT") or "")[:256]
    return raw


def record_user_consents(
    user: User,
    versions: list[LegalDocumentVersion],
    request: HttpRequest,
    *,
    record_ip: bool | None = None,
) -> None:
    """
    Создаёт записи согласия; идемпотентность за счёт UniqueConstraint и bulk_create(..., ignore_conflicts=True).
    IP берётся из settings.LEGAL_CONSENT_STORE_IP, если record_ip не передан явно.
    """
    if record_ip is None:
        record_ip = getattr(settings, "LEGAL_CONSENT_STORE_IP", False)
    ip = _client_ip(request) if record_ip else None
    ua = _short_ua(request)
    rows = [
        UserConsent(
            user=user,
            document_version=v,
            ip_address=ip,
            user_agent=ua,
        )
        for v in versions
    ]
    UserConsent.objects.bulk_create(rows, ignore_conflicts=True)


def verify_versions_unchanged(versions: list[LegalDocumentVersion]) -> bool:
    """Проверка, что содержимое в БД совпадает с checksum на момент принятия (опционально для споров)."""
    for v in versions:
        expected = hashlib.sha256(v.content_markdown.encode("utf-8")).hexdigest()
        if v.content_checksum != expected:
            return False
    return True
