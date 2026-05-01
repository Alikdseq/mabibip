"""Уведомления администраторам о заявках владельцев СТО (премодерация)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.mail import mail_admins
from django.urls import reverse

User = get_user_model()


def mail_admins_sto_registration_pending(
    *,
    user: User,
    station_name: str,
    city_label: str,
    executor_kind_display: str,
) -> None:
    """Письмо в ADMINS (django.core.mail.mail_admins). При пустом ADMINS тихо пропускается."""
    try:
        admin_path = reverse("admin:users_user_change", args=[user.pk])
    except Exception:
        admin_path = f"/secure-admin/users/user/{user.pk}/change/"
    subject = f"[МаБибип] Новая заявка СТО: {station_name}"
    body = (
        f"Требуется проверка заявки владельца СТО.\n\n"
        f"Телефон (логин): {user.phone}\n"
        f"Email: {user.email or '—'}\n"
        f"Название / имя: {station_name}\n"
        f"Город: {city_label}\n"
        f"Тип: {executor_kind_display}\n"
        f"Статус модерации: {user.get_sto_moderation_status_display()}\n\n"
        f"Карточка пользователя в админке: {admin_path}\n"
        "После проверки установите «Модерация заявки СТО» = «Одобрено» и при необходимости включите станцию в каталоге.\n"
    )
    mail_admins(subject, body, fail_silently=True)
