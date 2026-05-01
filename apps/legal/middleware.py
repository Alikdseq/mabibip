"""
Доступ владельца СТО в /sto/cabinet/* только после принятия актуальной оферты СТО.
См. PLAN-FULL-TZ-ATOMIC F0 + документ 07 (минимизация обхода бизнес-правил).

Премодерация: до статуса «Одобрено» доступны только страницы ожидания/отказа.
"""

from __future__ import annotations

from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.utils.deprecation import MiddlewareMixin

from apps.users.models import User

from .models import DocumentKey, UserConsent, get_current_version


class StoOfferConsentMiddleware(MiddlewareMixin):
    """Редирект на страницу принятия оферты СТО, если нет согласия на текущую версию."""

    def process_request(self, request):
        path = request.path
        if not path.startswith("/sto/cabinet/"):
            return None
        user = request.user
        if not user.is_authenticated or not getattr(user, "is_sto_owner", False):
            return None
        try:
            match = resolve(path)
        except Resolver404:
            return None
        if getattr(match, "namespace", None) != "sto_owner":
            return None

        mod_status = getattr(user, "sto_moderation_status", User.StoModerationStatus.APPROVED)
        if mod_status == User.StoModerationStatus.PENDING:
            if match.url_name == "pending_moderation":
                return None
            return redirect("sto_owner:pending_moderation")
        if mod_status == User.StoModerationStatus.REJECTED:
            if match.url_name == "moderation_rejected":
                return None
            return redirect("sto_owner:moderation_rejected")

        current = get_current_version(DocumentKey.STO_OFFER)
        if current is None:
            # Пока документ не загружен (например, чистая dev-БД) — не блокируем; в проде обязателен seed.
            return None
        if UserConsent.objects.filter(user=user, document_version=current).exists():
            return None
        return redirect("legal:sto_consent")
