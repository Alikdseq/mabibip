"""
Единая семантика «непрочитано» для поддержки.

- Для пользователя: есть ответ поддержки (is_staff_reply, не авто-сообщение), созданный
  позже, чем user_last_read_at (последний просмотр переписки в ЛК).
- Для персонала ERP: есть сообщение пользователя (не системное), созданное позже,
  чем staff_last_read_at (последний просмотр тикета в ERP).

Метки времени обновляются при открытии детальной страницы соответствующей стороной.
"""

from __future__ import annotations

from django.db.models import DateTimeField, F, OuterRef, Q, Subquery
from django.utils import timezone

from .models import SupportMessage, SupportTicket


def _latest_staff_message_time_subq():
    return Subquery(
        SupportMessage.objects.filter(
            ticket_id=OuterRef("pk"),
            is_staff_reply=True,
            is_system_auto=False,
        )
        .order_by("-created_at", "-pk")
        .values("created_at")[:1],
        output_field=DateTimeField(),
    )


def _latest_user_message_time_subq():
    return Subquery(
        SupportMessage.objects.filter(
            ticket_id=OuterRef("pk"),
            is_staff_reply=False,
            is_system_auto=False,
            author_id__isnull=False,
        )
        .order_by("-created_at", "-pk")
        .values("created_at")[:1],
        output_field=DateTimeField(),
    )


def support_unread_tickets_for_user_qs(user):
    """Тикеты пользователя с непрочитанным ответом поддержки."""
    return (
        SupportTicket.objects.filter(user=user)
        .annotate(_last_staff=_latest_staff_message_time_subq())
        .filter(_last_staff__isnull=False)
        .filter(Q(user_last_read_at__isnull=True) | Q(_last_staff__gt=F("user_last_read_at")))
    )


def support_unread_count_for_user(user) -> int:
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    return support_unread_tickets_for_user_qs(user).count()


def support_unread_tickets_for_staff_qs():
    """Тикеты, где есть новое сообщение пользователя с точки зрения ERP."""
    return (
        SupportTicket.objects.annotate(_last_user=_latest_user_message_time_subq())
        .filter(_last_user__isnull=False)
        .filter(Q(staff_last_read_at__isnull=True) | Q(_last_user__gt=F("staff_last_read_at")))
    )


def support_unread_count_for_staff() -> int:
    return support_unread_tickets_for_staff_qs().count()


def ticket_unread_for_user(ticket: SupportTicket) -> bool:
    return support_unread_tickets_for_user_qs(ticket.user).filter(pk=ticket.pk).exists()


def ticket_unread_for_staff(ticket: SupportTicket) -> bool:
    return support_unread_tickets_for_staff_qs().filter(pk=ticket.pk).exists()


def mark_ticket_read_by_user(ticket_id: int, *, user_id: int) -> None:
    SupportTicket.objects.filter(pk=ticket_id, user_id=user_id).update(user_last_read_at=timezone.now())


def mark_ticket_read_by_staff(ticket_id: int) -> None:
    SupportTicket.objects.filter(pk=ticket_id).update(staff_last_read_at=timezone.now())
