"""Ключ сайта reCAPTCHA v3 для шаблонов (без секретов)."""

from django.conf import settings

from .email_verification_access import email_verification_needed


def vk_oauth(request):
    """Публичный app id и флаги для кнопок VK (секрет только в env на сервере)."""
    cid = (getattr(settings, "VK_CLIENT_ID", None) or "").strip()
    secret = (getattr(settings, "VK_CLIENT_SECRET", None) or "").strip()
    enabled = bool(cid and secret)
    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    redirect_allauth = f"{base}/oauth/vk/login/callback/" if base else ""
    redirect_alias = f"{base}/accounts/vk/login/callback/" if base else ""
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
