from __future__ import annotations

from django import template

from apps.chat.booking_inbox_services import user_unread_total_for_header
from apps.chat.inbox_services import direct_unread_total_for_owner
from apps.users.models import User

register = template.Library()


@register.simple_tag
def client_booking_unread_count(user) -> int:
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    return int(user_unread_total_for_header(user))


@register.simple_tag
def booking_unread_count(user) -> int:
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    return int(user_unread_total_for_header(user))


@register.simple_tag
def header_chats_unread_total(user) -> int:
    """
    Бейдж «Чаты» в шапке: booking + (для клиента) direct к СТО + ad-direct;
    для одобренного владельца СТО дополнительно direct от клиентов станций.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    n = int(user_unread_total_for_header(user))
    if (
        getattr(user, "is_sto_owner", False)
        and getattr(user, "sto_moderation_status", None) == User.StoModerationStatus.APPROVED
    ):
        n += int(direct_unread_total_for_owner(user))
    return n

