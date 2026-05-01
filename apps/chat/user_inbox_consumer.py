from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.booking_inbox_services import user_unread_total_for_header


class UserInboxConsumer(AsyncWebsocketConsumer):
    """
    WS: /ws/user-inbox/
    Назначение: realtime-бейджи непрочитанных (booking-чаты).

    Auth: session (AuthMiddlewareStack).
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.group_name = f"user_inbox_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Стартовое значение
        count = await self._unread_count(user)
        await self.send(text_data=json.dumps({"type": "inbox", "booking_unread": int(count)}, ensure_ascii=False))

        # Непросмотренные toast-события (чтобы не терялись при оффлайне)
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
                    "booking_unread": int(event.get("booking_unread", 0)),
                },
                ensure_ascii=False,
            )
        )

    async def review_prompt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "review_prompt",
                    "booking_id": int(event.get("booking_id", 0) or 0),
                    "station_name": str(event.get("station_name") or ""),
                },
                ensure_ascii=False,
            )
        )

    async def reschedule_prompt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "reschedule_prompt",
                    "booking_id": int(event.get("booking_id", 0) or 0),
                    "station_name": str(event.get("station_name") or ""),
                    "slot_summary": str(event.get("slot_summary") or ""),
                    "owner_message": str(event.get("owner_message") or ""),
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

    async def _unread_count(self, user):
        return await self._unread_count_sync(user.pk)

    @database_sync_to_async
    def _unread_count_sync(self, user_id: int) -> int:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.get(pk=user_id)
        return int(user_unread_total_for_header(u))

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

