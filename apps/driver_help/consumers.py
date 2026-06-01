# -*- coding: utf-8 -*-

import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.driver_help.realtime import HELP_FEED_GROUP


class HelpFeedConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(HELP_FEED_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(HELP_FEED_GROUP, self.channel_name)

    async def help_feed_event(self, event):
        await self.send(text_data=json.dumps({"event": event["event"], "payload": event["payload"]}))
