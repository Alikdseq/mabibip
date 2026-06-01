# -*- coding: utf-8 -*-

from __future__ import annotations

from django.utils import timezone

from apps.driver_help.display import help_author_label, help_author_phone_e164
from apps.driver_help.models import DriverHelpRequest, HelpRequestStatus
from apps.driver_help.realtime import broadcast_help_event


def active_help_count() -> int:
    return DriverHelpRequest.objects.filter(status=HelpRequestStatus.ACTIVE).count()


def help_to_payload(req: DriverHelpRequest) -> dict:
    return {
        "id": req.pk,
        "message": req.message,
        "author_label": help_author_label(req.author),
        "created_at": req.created_at.isoformat(),
    }


def create_help_request(*, author, message: str) -> DriverHelpRequest:
    active = DriverHelpRequest.objects.filter(
        author=author,
        status=HelpRequestStatus.ACTIVE,
    ).count()
    if active >= 3:
        raise ValueError("У вас уже есть активные обращения. Дождитесь отклика или закройте старые.")
    text = (message or "").strip()
    if len(text) < 5:
        raise ValueError("Опишите ситуацию подробнее (минимум 5 символов).")
    req = DriverHelpRequest.objects.create(author=author, message=text[:500])
    broadcast_help_event("help_new", help_to_payload(req))
    return req


def resolve_help_request(*, req: DriverHelpRequest, resolver) -> str:
    if req.status != HelpRequestStatus.ACTIVE:
        raise ValueError("Обращение уже закрыто.")
    req.status = HelpRequestStatus.RESOLVED
    req.resolved_by = resolver
    req.resolved_at = timezone.now()
    req.save(update_fields=["status", "resolved_by", "resolved_at"])
    broadcast_help_event("help_resolved", {"id": req.pk})
    return help_author_phone_e164(req.author)
