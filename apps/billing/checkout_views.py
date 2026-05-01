"""Заглушка онлайн-оплаты ЮKassa (до включения YOOKASSA_ENABLED и боевых ключей)."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import render


def yookassa_checkout_info(request):
    """
    Страница-заглушка: состояние интеграции и что сделать для включения.
    Реальный Payment.create будет здесь после активации флага и credentials.
    """
    enabled = getattr(settings, "YOOKASSA_ENABLED", False)
    has_secret = bool(getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "").strip())
    return render(
        request,
        "billing/yookassa_checkout_info.html",
        {
            "yookassa_enabled": enabled,
            "webhook_secret_configured": has_secret,
        },
    )
