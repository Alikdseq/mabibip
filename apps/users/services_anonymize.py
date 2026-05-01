"""Право на удаление аккаунта: анонимизация ПДн с сохранением заказов для СТО (ТЗ, фаза F1.1.7)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


@transaction.atomic
def anonymize_user(user: User) -> None:
    """
    Пользователь не удаляется из БД (FK заказов), но ПДн стираются/заменяются.
    Уникальность phone/email сохраняем через случайный суффикс.
    """
    suffix = uuid.uuid4().hex[:16]
    user.phone = f"deleted_{suffix}"
    user.email = None
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.is_phone_verified = False
    user.email_verified = False
    user.email_verification_token = ""
    user.set_unusable_password()
    user.save(
        update_fields=[
            "phone",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_phone_verified",
            "email_verified",
            "email_verification_token",
            "password",
        ]
    )
