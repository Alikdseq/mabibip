from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer

from .realtime import user_calls_group


class CallsConsumer(AsyncWebsocketConsumer):
    """
    WS: /ws/calls/
    Назначение: realtime-события звонков (incoming/accepted/ended/...).

    Auth: session (AuthMiddlewareStack в ASGI).
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.group_name = user_calls_group(int(user.pk))
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Сокет только для доставки событий; управление — через REST /api/calls/*
        return

    async def calls_event(self, event):
        payload = event.get("payload") or {}
        await self.send(text_data=json.dumps(payload, ensure_ascii=False))

