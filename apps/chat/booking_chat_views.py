from __future__ import annotations

from datetime import datetime, timezone as dt_tz

from django.contrib.auth.decorators import login_required
from django.db.models import DateTimeField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.chat.models import ChatRoom, ChatRoomLastRead, Message
from apps.users.display import user_display_name


def _epoch():
    return datetime(1970, 1, 1, tzinfo=dt_tz.utc)


def _rooms_for_user(user):
    return (ChatRoom.objects.filter(booking__client=user) | ChatRoom.objects.filter(booking__station__owner=user)).select_related(
        "booking__station__owner",
        "booking__client",
        "booking__station",
    )


def _user_may_access_room(user, room: ChatRoom) -> bool:
    b = room.booking
    return b.client_id == user.pk or b.station.owner_id == user.pk


def _approved_sto(user) -> bool:
    from apps.users.models import User

    return (
        user.is_authenticated
        and getattr(user, "is_sto_owner", False)
        and user.sto_moderation_status == User.StoModerationStatus.APPROVED
    )


@login_required
def cabinet_chat_list(request):
    u = request.user
    last_msg_sq = (
        Message.objects.filter(room=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=u).values("last_read_at")[:1]

    rooms = _rooms_for_user(u).annotate(
        last_message_text=Subquery(last_msg_sq.values("text")[:1]),
        last_message_at=Subquery(last_msg_sq.values("created_at")[:1]),
        last_read_at=Coalesce(Subquery(last_read_sq), Value(_epoch(), output_field=DateTimeField())),
    ).order_by("-last_message_at", "-created_at", "-pk")

    items = []
    for r in rooms:
        unread = (
            Message.objects.filter(room=r)
            .exclude(sender=u)
            .filter(created_at__gt=r.last_read_at)
            .count()
        )
        items.append({"room": r, "unread": int(unread)})

    return render(
        request,
        "users/cabinet/chats_list.html",
        {"cabinet_section": "chats", "items": items},
    )


@login_required
def cabinet_chat_detail(request, room_id: int):
    u = request.user
    room = get_object_or_404(
        ChatRoom.objects.select_related("booking__station__owner", "booking__client", "booking__station"),
        pk=room_id,
    )
    if not _user_may_access_room(u, room):
        raise Http404

    # Помечаем как прочитанное при открытии
    ChatRoomLastRead.objects.update_or_create(room=room, user=u, defaults={"last_read_at": timezone.now()})

    msgs = (
        Message.objects.filter(room=room)
        .select_related("sender")
        .order_by("created_at", "pk")
    )

    booking = room.booking
    other = booking.station.owner if booking.client_id == u.pk else booking.client
    ws_path = f"/ws/chat/{booking.pk}/"
    peer_display = user_display_name(
        other,
        fallback=booking.station.name if booking.client_id == u.pk else "Клиент",
    )

    return render(
        request,
        "users/cabinet/chat_detail.html",
        {
            "cabinet_section": "chats",
            "room": room,
            "booking": booking,
            "other_user": other,
            "chat_messages": msgs,
            "chat_ws_path": ws_path,
            "peer_display": peer_display,
            "peer_user_id": int(other.pk),
            "call_context_kind": "booking_chat",
            "call_context_id": int(room.pk),
        },
    )


@login_required
def sto_owner_booking_chat_list(request):
    if not _approved_sto(request.user):
        raise Http404
    u = request.user

    last_msg_sq = (
        Message.objects.filter(room=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=u).values("last_read_at")[:1]

    rooms = ChatRoom.objects.filter(booking__station__owner=u).select_related(
        "booking__station__owner",
        "booking__client",
        "booking__station",
    ).annotate(
        last_message_text=Subquery(last_msg_sq.values("text")[:1]),
        last_message_at=Subquery(last_msg_sq.values("created_at")[:1]),
        last_read_at=Coalesce(Subquery(last_read_sq), Value(_epoch(), output_field=DateTimeField())),
    ).order_by("-last_message_at", "-created_at", "-pk")

    items = []
    for r in rooms:
        unread = (
            Message.objects.filter(room=r)
            .exclude(sender=u)
            .filter(created_at__gt=r.last_read_at)
            .count()
        )
        items.append({"room": r, "unread": int(unread)})

    return render(
        request,
        "sto_owner/booking_chats_list.html",
        {"items": items},
    )


@login_required
def sto_owner_booking_chat_detail(request, room_id: int):
    if not _approved_sto(request.user):
        raise Http404
    u = request.user

    room = get_object_or_404(
        ChatRoom.objects.select_related("booking__station__owner", "booking__client", "booking__station"),
        pk=room_id,
        booking__station__owner=u,
    )

    ChatRoomLastRead.objects.update_or_create(room=room, user=u, defaults={"last_read_at": timezone.now()})

    msgs = (
        Message.objects.filter(room=room)
        .select_related("sender")
        .order_by("created_at", "pk")
    )

    booking = room.booking
    ws_path = f"/ws/chat/{booking.pk}/"
    peer_display = user_display_name(booking.client, fallback=booking.client.phone)

    return render(
        request,
        "sto_owner/booking_chat_detail.html",
        {
            "room": room,
            "booking": booking,
            "client_user": booking.client,
            "chat_messages": msgs,
            "chat_ws_path": ws_path,
            "peer_display": peer_display,
            "peer_user_id": int(booking.client_id),
            "call_context_kind": "booking_chat",
            "call_context_id": int(room.pk),
        },
    )

