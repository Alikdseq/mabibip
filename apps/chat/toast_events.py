from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


def _send_group(group: str, message: dict) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(group, message)


def enqueue_user_toast(*, user_id: int, kind: str, payload: dict) -> int:
    """Создать toast-событие для пользователя (клиента) и отправить в WS (best-effort)."""
    from apps.chat.models import UserToastEvent

    ev = UserToastEvent.objects.create(user_id=int(user_id), kind=str(kind), payload=payload or {})
    _send_group(
        f"user_inbox_{user_id}",
        {"type": "toast.event", "event_id": ev.pk, "kind": ev.kind, "payload": ev.payload},
    )
    return int(ev.pk)


def enqueue_owner_toast(*, owner_user_id: int, kind: str, payload: dict) -> int:
    """Toast для владельца СТО. Шлём в user_inbox (сокет есть у любого авторизованного пользователя)."""
    from apps.chat.models import UserToastEvent

    ev = UserToastEvent.objects.create(user_id=int(owner_user_id), kind=str(kind), payload=payload or {})
    _send_group(
        f"user_inbox_{owner_user_id}",
        {"type": "toast.event", "event_id": ev.pk, "kind": ev.kind, "payload": ev.payload},
    )
    return int(ev.pk)


def mark_toasts_seen(*, user_id: int, event_ids: list[int]) -> int:
    """Отметить события как просмотренные. Возвращает число обновлённых строк."""
    from apps.chat.models import UserToastEvent

    ids = [int(x) for x in (event_ids or []) if int(x) > 0]
    if not ids:
        return 0
    now = timezone.now()
    return int(
        UserToastEvent.objects.filter(user_id=int(user_id), pk__in=ids, seen_at__isnull=True).update(seen_at=now)
    )

