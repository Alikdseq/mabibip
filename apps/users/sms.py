"""Отправка SMS с кодом OTP. Секреты и URL API — только из окружения (фаза F1.1.1)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import requests
from django.conf import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

def _mask_phone(phone_e164: str) -> str:
    s = (phone_e164 or "").strip()
    if len(s) <= 4:
        return "***"
    return f"{s[:2]}***{s[-2:]}"


def send_otp(phone_e164: str, code: str) -> None:
    """
    Доставляет одноразовый код на номер.
    SMS_BACKEND: console | smsru | smsaero (расширяйте по мере подключения провайдеров).
    """
    backend = getattr(settings, "SMS_BACKEND", os.getenv("SMS_BACKEND", "console"))
    text = f"Код подтверждения МаБибип: {code}"

    if backend == "console":
        # Никогда не логируем OTP-код и полный номер телефона (ПДн).
        logger.info("SMS backend=console to=%s (otp omitted)", _mask_phone(phone_e164))
        return

    if backend == "smsru":
        api_id = os.getenv("SMSRU_API_ID", "")
        if not api_id:
            raise RuntimeError("SMSRU_API_ID не задан")
        r = requests.post(
            "https://sms.ru/sms/send",
            data={
                "api_id": api_id,
                "to": phone_e164.replace("+", ""),
                "msg": text,
                "json": 1,
            },
            timeout=10,
        )
        r.raise_for_status()
        return

    if backend == "smsaero":
        email = os.getenv("SMSAERO_EMAIL", "")
        api_key = os.getenv("SMSAERO_API_KEY", "")
        if not email or not api_key:
            raise RuntimeError("SMSAERO_EMAIL / SMSAERO_API_KEY не заданы")
        r = requests.get(
            "https://gate.smsaero.ru/v2/sms/send",
            params={"number": phone_e164, "text": text, "sign": "SMS Aero"},
            auth=(email, api_key),
            timeout=10,
        )
        r.raise_for_status()
        return

    raise ValueError(f"Неизвестный SMS_BACKEND: {backend}")
