# -*- coding: utf-8 -*-
"""Флаги упрощённой регистрации (вкл/выкл без удаления кода)."""

from __future__ import annotations

from django.conf import settings

from .models import User


def registration_lite_enabled() -> bool:
    """Упрощённый UX: одна галочка, без email, без reCAPTCHA/rate limit на register_start."""
    return bool(getattr(settings, "DRIVER_REGISTRATION_LITE", True))


def is_registration_lite(role: str | None = None) -> bool:
    if not registration_lite_enabled():
        return False
    if role is None:
        return True
    return (role or "").strip() in dict(User.BusinessRole.choices)


def driver_registration_lite_enabled() -> bool:
    return registration_lite_enabled()


def is_driver_registration_lite(role: str | None) -> bool:
    return is_registration_lite(role)