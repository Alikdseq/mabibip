"""Синхронная отправка сообщения в чат по записи (fallback при недоступном WebSocket)."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh
from apps.chat.models import ChatRoom, Message
from apps.chat.rate_limit import allow_message_send


def post_booking_room_text_message(*, user, room_id: int, text: str) -> tuple[str | None, dict | None, int]:
    """
    Возвращает (error_code, message_payload, http_status).
    error_code None при успехе; message_payload — dict для JSON ответа.
    """
    try:
        allowed = allow_message_send(user_id=user.pk)
    except RuntimeError:
        return "temporarily_unavailable", None, 503
    if not allowed:
        return "rate_limited", None, 429

    text = (text or "").strip()
    if not text:
        return "empty_message", None, 400

    room = (
        ChatRoom.objects.select_related("booking__station__owner", "booking__client")
        .filter(pk=room_id)
        .first()
    )
    if not room:
        return "not_found", None, 404
    b = room.booking
    if not (b.client_id == user.pk or b.station.owner_id == user.pk):
        return "forbidden", None, 403

    if not room.can_post_messages():
        return "room_closed", None, 400

    msg = Message(room=room, sender_id=user.pk, text=text)
    if user.pk == b.client_id:
        msg.read_by_client = True
        msg.read_by_owner = False
    else:
        msg.read_by_owner = True
        msg.read_by_client = False

    msg.full_clean()
    msg.save()

    out = {
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }

    group_name = f"chat_room_{room.pk}"
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat.message",
                "id": out["id"],
                "sender_id": out["sender_id"],
                "text": out["text"],
                "created_at": out["created_at"],
            },
        )

    broadcast_booking_inbox_refresh(user.pk)
    other_uid = b.station.owner_id if user.pk == b.client_id else b.client_id
    broadcast_booking_inbox_refresh(other_uid)

    return None, out, 200
