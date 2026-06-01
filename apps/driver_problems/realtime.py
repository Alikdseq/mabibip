# -*- coding: utf-8 -*-

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

PROBLEMS_FEED_GROUP = "driver_problems_feed"


def broadcast_problem_event(event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        PROBLEMS_FEED_GROUP,
        {"type": "problem.feed.event", "event": event_type, "payload": payload},
    )
