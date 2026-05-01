from django import template

from apps.chat.inbox_services import direct_unread_total_for_owner

register = template.Library()


@register.simple_tag
def sto_owner_direct_unread_count(user) -> int:
    if not user.is_authenticated or not getattr(user, "is_sto_owner", False):
        return 0
    if getattr(user, "sto_moderation_status", None) != "approved":
        return 0
    return direct_unread_total_for_owner(user)
