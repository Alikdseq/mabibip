"""Проверка Google reCAPTCHA v2/v3 на сервере (фаза F1.1.4, документ 07 B.2)."""

from __future__ import annotations

import logging
import os

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class RecaptchaError(Exception):
    pass


def verify_recaptcha(*, token: str, action: str, remote_ip: str | None) -> None:
    """
    Бросает RecaptchaError при невалидном токене (v2/v3) или низком score (v3).
    В тестах: RECAPTCHA_SKIP=True — пропуск проверки.
    """
    if getattr(settings, "RECAPTCHA_SKIP", False):
        return
    version = (getattr(settings, "RECAPTCHA_VERSION", "v3") or "v3").strip().lower()
    secret = (
        (getattr(settings, "RECAPTCHA_SECRET_KEY", None) or "")
        or os.getenv("RECAPTCHA_SECRET_KEY", "")
        or os.getenv("RECAPTCHA_PRIVATE_KEY", "")
    ).strip()
    if not secret:
        raise RecaptchaError(
            "Сервер не настроен для проверки капчи (RECAPTCHA_SECRET_KEY или RECAPTCHA_PRIVATE_KEY).",
        )
    if not token:
        if version == "v2":
            raise RecaptchaError("Поставьте галочку «Я не робот».")
        raise RecaptchaError("Пройдите проверку «Я не робот».")

    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": secret,
            "response": token,
            "remoteip": remote_ip or "",
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        logger.warning("recaptcha failed: %s", data)
        raise RecaptchaError("Проверка безопасности не пройдена.")
    if version == "v3":
        if data.get("action") != action:
            raise RecaptchaError("Несоответствие действия капчи.")
        score = float(data.get("score", 0))
        min_score = float(getattr(settings, "RECAPTCHA_MIN_SCORE", 0.5))
        if score < min_score:
            raise RecaptchaError("Подозрительная активность. Попробуйте позже.")
