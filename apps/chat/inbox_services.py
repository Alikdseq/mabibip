"""Счётчик непрочитанных direct-чатов и рассылка в кабинет СТО по WebSocket."""

from __future__ import annotations

from datetime import datetime, timezone as dt_tz

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import DateTimeField, F, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


def direct_unread_total_for_owner(owner) -> int:
    """Сколько сообщений от клиентов ещё не «просмотрены» владельцем (по всем открытым тредам)."""
    from apps.chat.models import StationDirectMessage

    epoch = datetime(1970, 1, 1, tzinfo=dt_tz.utc)
    return StationDirectMessage.objects.filter(
        thread__station__owner=owner,
        thread__owner_archived_at__isnull=True,
        sender_id=F("thread__client_id"),
        created_at__gt=Coalesce(F("thread__owner_read_up_to"), Value(epoch, output_field=DateTimeField())),
    ).count()


def broadcast_sto_owner_inbox_refresh(owner_user_id: int) -> None:
    """Обновить бейджи у владельца через WebSocket (чаты + заявки)."""
    from apps.users.models import User

    owner = User.objects.filter(pk=owner_user_id).first()
    if not owner:
        return
    from apps.bookings.constants import BookingStatus
    from apps.bookings.models import Booking

    direct_unread = direct_unread_total_for_owner(owner)
    booking_pending = Booking.objects.filter(station__owner=owner, status=BookingStatus.PENDING).count()
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"sto_owner_inbox_{owner_user_id}",
        {"type": "inbox.refresh", "direct_unread": int(direct_unread), "booking_pending": int(booking_pending)},
    )


def mark_direct_threads_read_for_owner(owner) -> None:
    """Считать все переписки просмотренными (сброс непрочитанного)."""
    from apps.chat.models import StationDirectThread

    now = timezone.now()
    StationDirectThread.objects.filter(station__owner=owner, owner_archived_at__isnull=True).update(
        owner_read_up_to=now
    )
