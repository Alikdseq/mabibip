"""WebSocket: /ws/ad-direct/<thread_id>/ — чат покупатель ↔ продавец по объявлению."""

from __future__ import annotations

import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AdDirectChatConsumer(AsyncWebsocketConsumer):
    """Доступ: seller или buyer треда."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        try:
            self.thread_id = int(self.scope["url_route"]["kwargs"]["thread_id"])
        except (ValueError, KeyError, TypeError):
            await self.close(code=4400)
            return

        ok = await self._user_may_access(user_id=user.pk, thread_id=self.thread_id)
        if not ok:
            await self.close(code=4403)
            return

        self.group_name = f"ad_direct_{self.thread_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Сообщения создаются через HTTP POST; сокет только для доставки.
        pass

    async def direct_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "id": event.get("id"),
                    "sender_id": event.get("sender_id"),
                    "text": event.get("text"),
                    "created_at": event.get("created_at"),
                },
                ensure_ascii=False,
            )
        )

    @sync_to_async
    def _user_may_access(self, *, user_id: int, thread_id: int) -> bool:
        from apps.chat.models import AdDirectThread

        try:
            t = AdDirectThread.objects.only("buyer_id", "seller_id").get(pk=thread_id)
        except AdDirectThread.DoesNotExist:
            return False
        return t.buyer_id == user_id or t.seller_id == user_id

