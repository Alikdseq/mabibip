"""Отправка письма с подтверждением email (МаБибип, без Celery)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def _absolute_verify_url(request: HttpRequest | None, uidb64: str, token: str) -> str:
    path = reverse("users:verify_email", kwargs={"uidb64": uidb64, "token": token})
    base = (getattr(settings, "SITE_BASE_URL", None) or "").rstrip("/")
    if base:
        return f"{base}{path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_registration_verification_email(
    *,
    request: HttpRequest | None,
    user,
    uidb64: str,
    token: str,
) -> None:
    if not user.email or not token:
        return
    url = _absolute_verify_url(request, uidb64, token)
    subject = "Подтвердите email — МаБибип"
    ctx = {"user": user, "verify_url": url, "site_name": "МаБибип"}
    body_txt = render_to_string("users/email/email_verify_body.txt", ctx)
    body_html = render_to_string("users/email/email_verify_body.html", ctx)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "webmaster@localhost"
    try:
        send_mail(
            subject,
            body_txt,
            from_email,
            [user.email],
            fail_silently=False,
            html_message=body_html,
        )
    except Exception:
        logger.exception("send_registration_verification_email failed for user_id=%s", user.pk)
        raise
