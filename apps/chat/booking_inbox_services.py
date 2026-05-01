from __future__ import annotations

from datetime import datetime, timezone as dt_tz

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import DateTimeField, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce


def booking_unread_total_for_user(user) -> int:
    """
    Суммарное число непрочитанных сообщений в booking-чатах для пользователя.

    Источник истины: ChatRoomLastRead.last_read_at.
    """
    from apps.chat.models import ChatRoom, ChatRoomLastRead, Message

    epoch = datetime(1970, 1, 1, tzinfo=dt_tz.utc)
    last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=user).values("last_read_at")[:1]

    rooms = ChatRoom.objects.filter(
        booking__client=user,
    ) | ChatRoom.objects.filter(
        booking__station__owner=user,
    )

    # Считаем по каждому руму: сообщения от НЕ user позже last_read_at
    # (фильтр по sender_id != user.id и created_at > last_read_at)
    # Чтобы не тянуть комнаты в память, считаем одним count по messages.
    return Message.objects.filter(
        room__in=rooms.values("pk"),
    ).exclude(
        sender=user,
    ).filter(
        created_at__gt=Coalesce(Subquery(last_read_sq), Value(epoch, output_field=DateTimeField())),
    ).count()


def direct_unread_total_for_client(user) -> int:
    """
    Непрочитанные сообщения в direct-чатах для клиента (водителя).
    Источник истины: StationDirectThread.client_read_up_to.
    """
    from apps.chat.models import StationDirectMessage

    epoch = datetime(1970, 1, 1, tzinfo=dt_tz.utc)
    return StationDirectMessage.objects.filter(
        thread__client=user,
        sender_id=F("thread__station__owner_id"),
        created_at__gt=Coalesce(F("thread__client_read_up_to"), Value(epoch, output_field=DateTimeField())),
    ).count()


def ad_direct_unread_total_for_user(user) -> int:
    """
    Непрочитанные сообщения в чатах по объявлениям.
    Источник истины: AdDirectThread.(buyer_read_up_to/seller_read_up_to).
    """
    from apps.chat.models import AdDirectMessage

    epoch = datetime(1970, 1, 1, tzinfo=dt_tz.utc)
    # user = buyer: считаем сообщения от seller после buyer_read_up_to
    as_buyer = AdDirectMessage.objects.filter(
        thread__buyer=user,
        sender_id=F("thread__seller_id"),
        created_at__gt=Coalesce(F("thread__buyer_read_up_to"), Value(epoch, output_field=DateTimeField())),
    ).count()
    # user = seller: считаем сообщения от buyer после seller_read_up_to
    as_seller = AdDirectMessage.objects.filter(
        thread__seller=user,
        sender_id=F("thread__buyer_id"),
        created_at__gt=Coalesce(F("thread__seller_read_up_to"), Value(epoch, output_field=DateTimeField())),
    ).count()
    return int(as_buyer + as_seller)


def user_unread_total_for_header(user) -> int:
    """
    Базовая сумма непрочитанного для пользователя (без station-direct владельца).

    - Клиент: чаты по записям + прямые к СТО + чаты по объявлениям (ad-direct).
    - Одобренный владелец СТО: чаты по записям + ad-direct; прямые от клиентов станций
      учитываются отдельно (`direct_unread_total_for_owner`) и суммируются в шаблоне
      тегом `header_chats_unread_total`.
    """
    if getattr(user, "is_sto_owner", False) and getattr(user, "sto_moderation_status", "") == "approved":
        return int(booking_unread_total_for_user(user) + ad_direct_unread_total_for_user(user))
    return int(booking_unread_total_for_user(user) + direct_unread_total_for_client(user) + ad_direct_unread_total_for_user(user))


def broadcast_booking_inbox_refresh(user_id: int) -> None:
    """Отправить пользователю обновление бейджа «Чаты» по WebSocket."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return
    count = user_unread_total_for_header(user)
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_inbox_{user_id}",
        {"type": "inbox.refresh", "booking_unread": int(count)},
    )


def broadcast_review_prompt(*, user_id: int, booking_id: int, station_name: str) -> None:
    """Показать пользователю toast «Оставьте отзыв» (best-effort через WebSocket)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_inbox_{user_id}",
        {
            "type": "review.prompt",
            "booking_id": int(booking_id),
            "station_name": station_name,
        },
    )


def broadcast_reschedule_prompt(
    *,
    user_id: int,
    booking_id: int,
    station_name: str,
    slot_summary: str,
    owner_message: str,
) -> None:
    """Уведомить клиента о предложении переноса времени (toast в браузере)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_inbox_{user_id}",
        {
            "type": "reschedule.prompt",
            "booking_id": int(booking_id),
            "station_name": station_name,
            "slot_summary": slot_summary,
            "owner_message": owner_message or "",
        },
    )


def broadcast_sto_reschedule_notice(
    *,
    owner_user_id: int,
    kind: str,
    booking_id: int,
    station_slug: str,
    client_phone: str,
    slot_summary: str = "",
    chat_url: str = "",
) -> None:
    """Уведомление владельцу СТО о решении клиента по переносу."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"sto_owner_inbox_{owner_user_id}",
        {
            "type": "sto.notice",
            "kind": str(kind),
            "booking_id": int(booking_id),
            "station_slug": station_slug,
            "client_phone": client_phone or "",
            "slot_summary": slot_summary or "",
            "chat_url": chat_url or "",
        },
    )

