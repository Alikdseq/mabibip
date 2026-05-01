from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def user_calls_group(user_id: int) -> str:
    return f"user_calls_{int(user_id)}"


def send_to_user(*, user_id: int, payload: dict) -> None:
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        user_calls_group(int(user_id)),
        {
            "type": "calls_event",
            "payload": payload,
        },
    )

