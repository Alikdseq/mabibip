"""Константы SMS/OTP и ограничений перебора (ТЗ + документ 07, B.2)."""

OTP_LENGTH = 4
OTP_EXPIRE_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_LOCKOUT_MINUTES = 15
OTP_RESEND_COOLDOWN_SECONDS = 60

# Лимит запросов кода с одного IP (в минуту) — дополнительно к cooldown по номеру.
OTP_IP_MAX_PER_MINUTE = 20
