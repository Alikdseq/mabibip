from __future__ import annotations

import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.files.base import ContentFile

from apps.bookings.constants import BookingStatus
from apps.chat.rate_limit import allow_message_send
from apps.chat.validators import validate_chat_attachment
from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WS: /ws/chat/<booking_id>/
    Аутентификация: session (AuthMiddlewareStack).
    ACL: только клиент брони или владелец СТО.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        booking_id = int(self.scope["url_route"]["kwargs"]["booking_id"])
        room_id = await self._get_or_create_room_id(booking_id=booking_id, user_id=user.pk)
        if room_id is None:
            await self.close(code=4403)
            return

        self.booking_id = booking_id
        self.room_id = room_id
        self.group_name = f"chat_room_{room_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        try:
            allowed = allow_message_send(user_id=user.pk)
        except RuntimeError:
            # Redis/rate-limit недоступны: лучше корректно деградировать, чем падать consumer'ом.
            await self.send_json({"type": "error", "detail": "temporarily_unavailable"})
            return
        if not allowed:
            await self.send_json({"type": "error", "detail": "rate_limited"})
            return

        try:
            payload = json.loads(text_data or "{}")
        except ValueError:
            await self.send_json({"type": "error", "detail": "invalid_json"})
            return

        if payload.get("type") == "ping":
            await self.send_json({"type": "pong", "t": payload.get("t")})
            return

        text = (payload.get("text") or "").strip()
        attachment = payload.get("attachment")
        filename = (payload.get("filename") or "").strip()

        # attachment как base64 запрещаем на этом этапе (чтобы не тащить большие payload через WS)
        if attachment is not None:
            await self.send_json({"type": "error", "detail": "attachment_not_supported_over_ws"})
            return

        ok = await self._can_post(user_id=user.pk, booking_id=self.booking_id)
        if not ok:
            await self.send_json({"type": "error", "detail": "room_closed"})
            return

        msg = await self._create_message(room_id=self.room_id, sender_id=user.pk, text=text)
        if msg is None:
            await self.send_json({"type": "error", "detail": "empty_message"})
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "id": msg["id"],
                "sender_id": msg["sender_id"],
                "text": msg["text"],
                "created_at": msg["created_at"],
            },
        )

        # Обновляем бейджи непрочитанных у обеих сторон (best-effort).
        try:
            other_user_id = await self._other_user_id(room_id=self.room_id, sender_id=user.pk)
            broadcast_booking_inbox_refresh(user.pk)
            if other_user_id:
                broadcast_booking_inbox_refresh(other_user_id)
        except Exception:
            logger.exception("booking inbox refresh failed")

    async def chat_message(self, event):
        # Нельзя делать {"type": "message", **event}: в event уже есть type=chat.message и перезапишет ключ.
        await self.send_json(
            {
                "type": "message",
                "id": event.get("id"),
                "sender_id": event.get("sender_id"),
                "text": event.get("text"),
                "created_at": event.get("created_at"),
            }
        )

    async def send_json(self, data: dict):
        await self.send(text_data=json.dumps(data, ensure_ascii=False))

    @sync_to_async
    def _get_or_create_room_id(self, *, booking_id: int, user_id: int) -> int | None:
        from apps.bookings.models import Booking
        from apps.chat.models import ChatRoom

        try:
            b = Booking.objects.select_related("station__owner", "client").get(pk=booking_id)
        except Booking.DoesNotExist:
            return None

        if b.status not in {
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.IN_PROGRESS,
            BookingStatus.COMPLETED,
            BookingStatus.CANCELED,
        }:
            return None

        if not (b.client_id == user_id or b.station.owner_id == user_id):
            return None

        room, _ = ChatRoom.objects.get_or_create(booking=b)
        # Закрываем комнату автоматически по финальным статусам.
        if b.status in {BookingStatus.COMPLETED, BookingStatus.CANCELED} and not room.is_closed:
            room.close()
        return room.pk

    @sync_to_async
    def _can_post(self, *, user_id: int, booking_id: int) -> bool:
        from apps.bookings.models import Booking
        from apps.chat.models import ChatRoom

        try:
            b = Booking.objects.select_related("station__owner", "client").get(pk=booking_id)
        except Booking.DoesNotExist:
            return False
        if not (b.client_id == user_id or b.station.owner_id == user_id):
            return False
        try:
            room = ChatRoom.objects.get(booking=b)
        except ChatRoom.DoesNotExist:
            return False
        if b.status in {BookingStatus.COMPLETED, BookingStatus.CANCELED}:
            room.close()
            return False
        return room.can_post_messages()

    @sync_to_async
    def _create_message(self, *, room_id: int, sender_id: int, text: str):
        from apps.chat.models import ChatRoom, Message

        room = ChatRoom.objects.select_related("booking__station__owner", "booking__client").get(pk=room_id)
        if not room.can_post_messages():
            return None
        msg = Message(room=room, sender_id=sender_id, text=text)

        booking = room.booking
        if sender_id == booking.client_id:
            msg.read_by_client = True
            msg.read_by_owner = False
        else:
            msg.read_by_owner = True
            msg.read_by_client = False

        msg.full_clean()
        msg.save()
        return {
            "id": msg.pk,
            "sender_id": msg.sender_id,
            "text": msg.text,
            "created_at": msg.created_at.isoformat(),
        }

    @sync_to_async
    def _other_user_id(self, *, room_id: int, sender_id: int) -> int | None:
        from apps.chat.models import ChatRoom

        room = ChatRoom.objects.select_related("booking__station__owner", "booking__client").get(pk=room_id)
        booking = room.booking
        if sender_id == booking.client_id:
            return booking.station.owner_id
        if sender_id == booking.station.owner_id:
            return booking.client_id
        return None

