"""Нормализация телефонов в E.164 (РФ по умолчанию) — единый формат в БД и для SMS."""

from __future__ import annotations

import re

import phonenumbers
from phonenumbers import NumberParseException


class PhoneValidationError(ValueError):
    pass


def normalize_to_e164(raw: str, *, region: str = "RU") -> str:
    """
    Преобразует ввод пользователя в E.164 (+7…).
    region='RU' позволяет принимать «9123456789» и «89123456789».
    """
    cleaned = (raw or "").strip()
    if not cleaned:
        raise PhoneValidationError("Укажите номер телефона.")
    # UX: принимаем ввод +7..., 7..., 8... и 10 цифр (РФ). Приводим к виду +7XXXXXXXXXX.
    digits = re.sub(r"\D+", "", cleaned)
    if digits:
        if len(digits) == 10:
            cleaned = f"+7{digits}"
        elif len(digits) == 11 and digits[0] in ("7", "8") and not cleaned.startswith("+"):
            cleaned = f"+7{digits[1:]}"
    try:
        num = phonenumbers.parse(cleaned, region)
    except NumberParseException as e:
        raise PhoneValidationError("Некорректный номер телефона.") from e
    if not phonenumbers.is_valid_number(num):
        raise PhoneValidationError("Номер телефона недействителен.")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
