# -*- coding: utf-8 -*-

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


HELP_FEED_GROUP = "driver_help_feed"


def broadcast_help_event(event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        HELP_FEED_GROUP,
        {"type": "help.feed.event", "event": event_type, "payload": payload},
    )
