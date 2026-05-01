from __future__ import annotations

from datetime import datetime, timezone as dt_tz

from django.db.models import DateTimeField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.booking_chat_http import post_booking_room_text_message
from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh, user_unread_total_for_header
from apps.chat.inbox_services import direct_unread_total_for_owner
from apps.chat.models import ChatRoom, ChatRoomLastRead, Message
from apps.chat.toast_events import mark_toasts_seen
from apps.users.models import User


def _epoch():
    return datetime(1970, 1, 1, tzinfo=dt_tz.utc)


def _user_may_access_room(user, room: ChatRoom) -> bool:
    b = room.booking
    return b.client_id == user.pk or b.station.owner_id == user.pk


class ChatMessagesPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 50


class HeaderInboxSummaryAPIView(APIView):
    """
    Счётчики для шапки «Чаты» без WebSocket (опрос при недоступном WS / ngrok → WSGI).
    Поля совпадают с логикой header-inbox.js + user/sto_owner consumers.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        user_inbox_unread = int(user_unread_total_for_header(u))
        sto_direct_unread = 0
        sto_booking_pending = 0
        if getattr(u, "is_sto_owner", False) and u.sto_moderation_status == User.StoModerationStatus.APPROVED:
            sto_direct_unread = int(direct_unread_total_for_owner(u))
            from apps.bookings.constants import BookingStatus
            from apps.bookings.models import Booking

            sto_booking_pending = int(
                Booking.objects.filter(station__owner=u, status=BookingStatus.PENDING).count()
            )
        return Response(
            {
                "user_inbox_unread": user_inbox_unread,
                "sto_direct_unread": sto_direct_unread,
                "sto_booking_pending": sto_booking_pending,
                "header_chats_unread": user_inbox_unread + sto_direct_unread,
            }
        )


class ChatRoomListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user

        rooms = (
            ChatRoom.objects.filter(booking__client=u)
            | ChatRoom.objects.filter(booking__station__owner=u)
        ).select_related("booking__station__owner", "booking__client", "booking__station")

        last_msg_sq = (
            Message.objects.filter(room=OuterRef("pk"))
            .order_by("-created_at", "-pk")
            .values("text", "created_at", "sender_id")[:1]
        )
        last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=u).values("last_read_at")[:1]

        # Берём данные последнего сообщения через 3 subquery
        rooms = rooms.annotate(
            last_message_text=Subquery(last_msg_sq.values("text")[:1]),
            last_message_at=Subquery(last_msg_sq.values("created_at")[:1]),
            last_message_sender_id=Subquery(last_msg_sq.values("sender_id")[:1]),
            last_read_at=Coalesce(Subquery(last_read_sq), Value(_epoch(), output_field=DateTimeField())),
        ).order_by("-last_message_at", "-created_at", "-pk")

        items = []
        for r in rooms:
            b = r.booking
            other = b.station.owner if b.client_id == u.pk else b.client
            unread = (
                Message.objects.filter(room=r)
                .exclude(sender=u)
                .filter(created_at__gt=r.last_read_at)
                .count()
            )
            items.append(
                {
                    "id": r.pk,
                    "booking_id": b.pk,
                    "is_closed": bool(r.is_closed),
                    "other_user": {
                        "id": other.pk,
                        "name": (getattr(other, "get_full_name", lambda: "")() or getattr(other, "phone", "") or "").strip(),
                        "role": "owner" if other.pk == b.station.owner_id else "client",
                    },
                    "station": {"id": b.station_id, "name": b.station.name, "slug": b.station.slug},
                    "last_message": {
                        "text": r.last_message_text or "",
                        "created_at": r.last_message_at.isoformat() if r.last_message_at else None,
                        "sender_id": int(r.last_message_sender_id) if r.last_message_sender_id else None,
                    },
                    "unread_count": int(unread),
                }
            )

        return Response({"results": items})


class ChatMessageListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = ChatMessagesPagination

    def get(self, request, room_id: int):
        u = request.user
        room = get_object_or_404(
            ChatRoom.objects.select_related("booking__station__owner", "booking__client", "booking__station"),
            pk=room_id,
        )
        if not _user_may_access_room(u, room):
            return Response({"detail": "forbidden"}, status=403)

        raw_after = (request.GET.get("after_id") or "").strip()
        if raw_after.isdigit():
            qs = (
                Message.objects.filter(room=room, pk__gt=int(raw_after))
                .select_related("sender")
                .order_by("created_at", "pk")[:200]
            )
            data = [
                {
                    "id": m.pk,
                    "sender_id": m.sender_id,
                    "text": m.text or "",
                    "attachment_url": m.attachment.url if m.attachment else None,
                    "created_at": m.created_at.isoformat(),
                }
                for m in qs
            ]
            return Response({"room_id": room.pk, "messages": data})

        qs = Message.objects.filter(room=room).select_related("sender").order_by("-created_at", "-pk")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [
            {
                "id": m.pk,
                "sender_id": m.sender_id,
                "text": m.text or "",
                "attachment_url": m.attachment.url if m.attachment else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in page
        ]
        return paginator.get_paginated_response({"room_id": room.pk, "messages": data})


class ChatMessageCreateAPIView(APIView):
    """POST текстового сообщения (если WebSocket недоступен — тот же эффект, что receive в ChatConsumer)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, room_id: int):
        text = ""
        if isinstance(request.data, dict):
            text = (request.data.get("text") or "").strip()
        err, payload, status = post_booking_room_text_message(user=request.user, room_id=room_id, text=text)
        if err:
            if err == "forbidden":
                return Response({"ok": False, "error": err}, status=403)
            if err == "not_found":
                return Response({"ok": False, "error": err}, status=404)
            return Response({"ok": False, "error": err}, status=status)
        return Response({"ok": True, "message": payload}, status=status)


class ChatMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id: int):
        u = request.user
        room = get_object_or_404(
            ChatRoom.objects.select_related("booking__station__owner", "booking__client"),
            pk=room_id,
        )
        if not _user_may_access_room(u, room):
            return Response({"detail": "forbidden"}, status=403)

        now = timezone.now()
        ChatRoomLastRead.objects.update_or_create(room=room, user=u, defaults={"last_read_at": now})

        # best-effort: сохраняем старые флаги read_by_* для совместимости/админки
        b = room.booking
        if u.pk == b.client_id:
            Message.objects.filter(room=room).exclude(sender=u).update(read_by_client=True)
        elif u.pk == b.station.owner_id:
            Message.objects.filter(room=room).exclude(sender=u).update(read_by_owner=True)

        broadcast_booking_inbox_refresh(u.pk)
        return Response({"ok": True, "last_read_at": now.isoformat()})


class ToastEventsMarkSeenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        if not isinstance(ids, list):
            return Response({"detail": "bad_request"}, status=400)
        n = mark_toasts_seen(user_id=request.user.pk, event_ids=ids)
        return Response({"ok": True, "updated": int(n)})

