"""Ключ сайта reCAPTCHA v3 для шаблонов (без секретов)."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.urls import reverse

from .email_verification_access import email_verification_needed


def _force_https_if_public(url: str) -> str:
    """
    VK ID отклоняет http redirect_uri на проде. За прокси иногда request.scheme=http при том, что снаружи HTTPS.
    """
    if not url or not url.startswith("http://"):
        return url
    if getattr(settings, "DEBUG", False):
        return url
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "testserver"}:
        return url
    return "https://" + url[7:]


def vk_oauth(request):
    """Публичный app id и флаги для кнопок VK (секрет только в env на сервере)."""
    cid = (getattr(settings, "VK_CLIENT_ID", None) or "").strip()
    secret = (getattr(settings, "VK_CLIENT_SECRET", None) or "").strip()
    enabled = bool(cid and secret)
    base = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    redirect_allauth = f"{base}/oauth/vk/login/callback/" if base else ""

    alias_path = reverse("users:vk_oauth_callback_alias")
    override = (getattr(settings, "VK_ID_REDIRECT_URI", "") or "").strip()

    if override:
        redirect_alias = override
    else:
        try:
            redirect_alias = request.build_absolute_uri(alias_path)
        except Exception:
            redirect_alias = ""
        if not redirect_alias and base:
            redirect_alias = f"{base}{alias_path}"

    redirect_alias = _force_https_if_public(redirect_alias)

    return {
        "vk_oauth_enabled": enabled,
        "vk_app_id": cid,
        "vk_oauth_redirect_allauth": redirect_allauth,
        "vk_oauth_redirect_alias": redirect_alias,
    }


def recaptcha_site_key(request):
    return {
        "RECAPTCHA_SITE_KEY": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
        "RECAPTCHA_VERSION": getattr(settings, "RECAPTCHA_VERSION", "v3"),
    }


def email_verification_notice(request):
    """Баннер в шапке: email указан, но не подтверждён."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if not email_verification_needed(request.user):
        return {}
    return {"show_email_verification_banner": True}
