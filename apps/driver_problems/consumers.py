import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.driver_problems.realtime import PROBLEMS_FEED_GROUP


class ProblemsFeedConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(PROBLEMS_FEED_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(PROBLEMS_FEED_GROUP, self.channel_name)

    async def problem_feed_event(self, event):
        await self.send(text_data=json.dumps({"event": event["event"], "payload": event["payload"]}))
