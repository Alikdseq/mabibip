"""Создание и проверка SMS-вызовов с защитой от перебора (фаза F1.1.2–F1.1.3)."""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

from apps.users.constants import (
    OTP_EXPIRE_SECONDS,
    OTP_IP_MAX_PER_MINUTE,
    OTP_LOCKOUT_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
)
from apps.users.models import PhoneVerificationChallenge, User
from apps.users.otp import generate_numeric_code, hash_otp, verify_otp
from apps.users.sms import send_otp


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def check_otp_rate_limits(*, phone_e164: str, request) -> None:
    """Бросает ValidationError-подобные RuntimeError или используем custom - use django ValidationError"""
    from django.core.exceptions import ValidationError

    ip = _client_ip(request)
    if ip:
        k = f"otp_ip_min:{ip}"
        n = cache.get(k, 0)
        if n >= OTP_IP_MAX_PER_MINUTE:
            raise ValidationError("Слишком много запросов. Подождите минуту.")
    ck = f"otp_cool:{phone_e164}"
    if cache.get(ck):
        raise ValidationError("Код уже отправлен. Подождите перед повторной отправкой.")


def start_phone_challenge(*, phone_e164: str, request) -> None:
    """Отправляет новый OTP и создаёт запись (после проверки лимитов)."""
    from django.core.exceptions import ValidationError

    check_otp_rate_limits(phone_e164=phone_e164, request=request)
    if User.objects.filter(phone=phone_e164).exists():
        raise ValidationError("Этот номер уже зарегистрирован. Войдите или восстановите пароль.")

    code = generate_numeric_code()
    ip = _client_ip(request)
    PhoneVerificationChallenge.objects.create(
        phone_e164=phone_e164,
        code_hash=hash_otp(phone_e164, code),
        last_ip=ip,
    )
    send_otp(phone_e164, code)
    cache.set(f"otp_cool:{phone_e164}", 1, OTP_RESEND_COOLDOWN_SECONDS)
    if ip:
        k = f"otp_ip_min:{ip}"
        try:
            cache.incr(k)
        except ValueError:
            cache.set(k, 1, 60)


def verify_phone_challenge(*, phone_e164: str, code: str, request) -> bool:
    """
    Проверяет код по последнему непросроченному challenge.
    Возвращает True при успехе; при исчерпании попыток — блокировка и False.
    """
    cutoff = timezone.now() - timezone.timedelta(seconds=OTP_EXPIRE_SECONDS)
    ch = (
        PhoneVerificationChallenge.objects.filter(phone_e164=phone_e164, created_at__gte=cutoff)
        .order_by("-created_at")
        .first()
    )
    if ch is None:
        return False
    if ch.is_locked():
        return False

    if not verify_otp(phone_e164, code, ch.code_hash):
        ch.attempts += 1
        if ch.attempts >= OTP_MAX_ATTEMPTS:
            ch.locked_until = timezone.now() + timezone.timedelta(minutes=OTP_LOCKOUT_MINUTES)
        ch.save(update_fields=["attempts", "locked_until"])
        return False

    return True


def is_phone_challenge_locked(phone_e164: str) -> bool:
    cutoff = timezone.now() - timezone.timedelta(seconds=OTP_EXPIRE_SECONDS)
    ch = (
        PhoneVerificationChallenge.objects.filter(phone_e164=phone_e164, created_at__gte=cutoff)
        .order_by("-created_at")
        .first()
    )
    return ch is not None and ch.is_locked()
