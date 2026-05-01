from __future__ import annotations

from django import template

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking

register = template.Library()


@register.simple_tag
def sto_pending_booking_count(user) -> int:
    """Сколько заявок pending у владельца СТО (для бейджа в меню)."""
    if not getattr(user, "is_authenticated", False):
        return 0
    if not getattr(user, "is_sto_owner", False):
        return 0
    if getattr(user, "sto_moderation_status", "") != "approved":
        return 0
    return int(Booking.objects.filter(station__owner=user, status=BookingStatus.PENDING).count())

