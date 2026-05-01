"""WebSocket: /ws/sto-owner/inbox/ — мгновенное обновление счётчика непрочитанных в кабинете СТО."""

from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.inbox_services import direct_unread_total_for_owner
from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking



class StoOwnerInboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        ok = await self._approved_sto(user.pk)
        if not ok:
            await self.close(code=4403)
            return
        self.group_name = f"sto_owner_inbox_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        direct_unread, booking_pending = await self._inbox_counts_async(user.pk)
        await self.send(
            text_data=json.dumps(
                {
                    "type": "inbox",
                    "direct_unread": int(direct_unread),
                    "booking_pending": int(booking_pending),
                },
                ensure_ascii=False,
            )
        )

        events = await self._unseen_toasts(user.pk)
        if events:
            await self.send(text_data=json.dumps({"type": "toast_events", "events": events}, ensure_ascii=False))

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def inbox_refresh(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "inbox",
                    "direct_unread": int(event.get("direct_unread", 0)),
                    "booking_pending": int(event.get("booking_pending", 0)),
                },
                ensure_ascii=False,
            )
        )

    async def sto_notice(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "sto_notice",
                    "kind": str(event.get("kind") or ""),
                    "booking_id": int(event.get("booking_id", 0) or 0),
                    "station_slug": str(event.get("station_slug") or ""),
                    "client_phone": str(event.get("client_phone") or ""),
                    "slot_summary": str(event.get("slot_summary") or ""),
                    "chat_url": str(event.get("chat_url") or ""),
                },
                ensure_ascii=False,
            )
        )

    async def toast_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "toast_event",
                    "event_id": int(event.get("event_id", 0) or 0),
                    "kind": str(event.get("kind") or ""),
                    "payload": event.get("payload") or {},
                },
                ensure_ascii=False,
            )
        )

    @database_sync_to_async
    def _approved_sto(self, user_id: int) -> bool:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            u = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return False
        return getattr(u, "is_sto_owner", False) and u.sto_moderation_status == User.StoModerationStatus.APPROVED

    @database_sync_to_async
    def _inbox_counts_async(self, user_id: int) -> tuple[int, int]:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.get(pk=user_id)
        direct_unread = direct_unread_total_for_owner(u)
        booking_pending = Booking.objects.filter(station__owner=u, status=BookingStatus.PENDING).count()
        return int(direct_unread), int(booking_pending)

    @database_sync_to_async
    def _unseen_toasts(self, user_id: int):
        from apps.chat.models import UserToastEvent

        qs = (
            UserToastEvent.objects.filter(user_id=int(user_id), seen_at__isnull=True)
            .order_by("created_at", "pk")[:20]
        )
        return [
            {"event_id": int(e.pk), "kind": e.kind, "payload": e.payload or {}}
            for e in qs
        ]
