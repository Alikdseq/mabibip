from django import template

from apps.support.unread import support_unread_count_for_staff, support_unread_count_for_user

register = template.Library()


@register.simple_tag
def support_user_unread_count(user) -> int:
    return support_unread_count_for_user(user)


@register.simple_tag
def support_staff_unread_count() -> int:
    return support_unread_count_for_staff()
