from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SupportMessage, SupportTicket, SupportTicketStatus

SUPPORT_TICKET_AUTO_ACK_TEXT = (
    "Спасибо, что написали нам. Ваш запрос уже получен и передан в поддержку — мы обязательно "
    "его рассмотрим и постараемся ответить как можно скорее. Если вы предложили идею по улучшению "
    "сервиса, мы тоже её сохраним: так «МаБибип» становятся удобнее для всех. Хорошего дня."
)


def _body_min_length() -> int:
    return int(getattr(settings, "SUPPORT_TICKET_BODY_MIN_LENGTH", 10))


def _max_new_tickets_per_hour() -> int:
    return int(getattr(settings, "SUPPORT_MAX_NEW_TICKETS_PER_HOUR", 5))


def create_ticket_with_initial_message(
    user,
    text: str,
    *,
    subject: str = "",
) -> SupportTicket:
    """
    Атомарно: тикет, первое сообщение пользователя, авто-подтверждение поддержки.
    Бросает ValueError при слишком коротком тексте или превышении лимита новых тикетов за час.
    """
    body = (text or "").strip()
    subj = (subject or "").strip()[:200]
    if len(body) < _body_min_length():
        raise ValueError(
            f"Текст обращения слишком короткий — минимум {_body_min_length()} символов."
        )

    since = timezone.now() - timedelta(hours=1)
    recent = SupportTicket.objects.filter(user=user, created_at__gte=since).count()
    if recent >= _max_new_tickets_per_hour():
        raise ValueError(
            "Слишком много обращений за последний час. Пожалуйста, подождите немного и попробуйте снова."
        )

    _ack_override = getattr(settings, "SUPPORT_TICKET_AUTO_ACK_TEXT", None)
    if isinstance(_ack_override, str) and _ack_override.strip():
        ack = _ack_override.strip()
    else:
        ack = SUPPORT_TICKET_AUTO_ACK_TEXT

    with transaction.atomic():
        ticket = SupportTicket.objects.create(
            user=user,
            subject=subj,
            status=SupportTicketStatus.OPEN,
        )
        SupportMessage.objects.create(
            ticket=ticket,
            author=user,
            body=body,
            is_staff_reply=False,
            is_system_auto=False,
        )
        SupportMessage.objects.create(
            ticket=ticket,
            author=None,
            body=ack,
            is_staff_reply=False,
            is_system_auto=True,
        )
        now = timezone.now()
        ticket.user_last_read_at = now
        ticket.save(update_fields=["user_last_read_at"])

    return ticket
