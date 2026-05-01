"""Генерация и проверка OTP без хранения открытого кода (HMAC + SECRET_KEY)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings


def generate_numeric_code(length: int = 4) -> str:
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def hash_otp(phone_e164: str, code: str) -> str:
    msg = f"{phone_e164}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def verify_otp(phone_e164: str, code: str, stored_hash: str) -> bool:
    expect = hash_otp(phone_e164, code)
    return hmac.compare_digest(expect, stored_hash)
