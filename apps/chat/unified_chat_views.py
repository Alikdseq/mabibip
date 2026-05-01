from __future__ import annotations

from datetime import datetime, timezone as dt_tz

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import DateTimeField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh
from apps.chat.inbox_services import broadcast_sto_owner_inbox_refresh
from apps.chat.models import (
    ChatRoom,
    ChatRoomLastRead,
    AdDirectMessage,
    AdDirectThread,
    Message as BookingMessage,
    StationDirectMessage,
    StationDirectThread,
)
from apps.chat.rate_limit import allow_message_send
from apps.users.display import user_avatar_url, user_display_name
from apps.users.models import User


def _epoch():
    return datetime(1970, 1, 1, tzinfo=dt_tz.utc)


def _wants_json(request) -> bool:
    accept = request.headers.get("Accept") or ""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in accept


def _approved_sto(user) -> bool:
    return (
        user.is_authenticated
        and getattr(user, "is_sto_owner", False)
        and user.sto_moderation_status == User.StoModerationStatus.APPROVED
    )


def _serialize_direct_message(msg: StationDirectMessage) -> dict:
    return {
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
        "created_at_display": date_format(timezone.localtime(msg.created_at), format="d.m.Y H:i"),
    }


def _sort_chat_items_by_last_at(items: list) -> list:
    min_dt = timezone.make_aware(datetime.min)
    return sorted(items, key=lambda x: (x["last_at"] or min_dt), reverse=True)


def _normalize_chats_tab(raw: str | None) -> str:
    t = (raw or "all").strip().lower()
    if t in ("booking", "direct"):
        return "masters"
    if t in ("all", "masters", "ads"):
        return t
    return "all"


@login_required
def cabinet_chats_unified(request):
    """
    Единый список чатов клиента: записи, прямые к СТО, чаты по объявлениям.
    """
    u = request.user

    # booking rooms
    last_booking_msg_sq = (
        BookingMessage.objects.filter(room=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=u).values("last_read_at")[:1]
    booking_rooms = (
        ChatRoom.objects.filter(booking__client=u)
        .select_related("booking__station", "booking__station__owner")
        .annotate(
            last_message_text=Subquery(last_booking_msg_sq.values("text")[:1]),
            last_message_at=Subquery(last_booking_msg_sq.values("created_at")[:1]),
            last_read_at=Coalesce(Subquery(last_read_sq), Value(_epoch(), output_field=DateTimeField())),
        )
    )

    booking_items = []
    for r in booking_rooms:
        unread = (
            BookingMessage.objects.filter(room=r)
            .exclude(sender=u)
            .filter(created_at__gt=r.last_read_at)
            .count()
        )
        booking_items.append(
            {
                "kind": "booking",
                "id": r.pk,
                "title": r.booking.station.name,
                "subtitle": f"Запись #{r.booking_id}",
                "last_text": (r.last_message_text or "").strip(),
                "last_at": r.last_message_at,
                "unread": int(unread),
                "url": reverse("cabinet:chat_detail", kwargs={"room_id": r.pk}),
            }
        )

    # direct threads
    last_direct_msg_sq = (
        StationDirectMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    direct_threads = (
        StationDirectThread.objects.filter(client=u)
        .select_related("station", "station__owner")
        .annotate(
            last_message_text_annot=Subquery(last_direct_msg_sq.values("text")[:1]),
            last_message_created_at=Subquery(last_direct_msg_sq.values("created_at")[:1]),
        )
        .order_by("-last_message_at", "-updated_at", "-pk")
    )
    station_direct_items = []
    for t in direct_threads:
        cutoff = t.client_read_up_to or timezone.make_aware(_epoch().replace(tzinfo=dt_tz.utc))
        unread = StationDirectMessage.objects.filter(thread=t, sender_id=t.station.owner_id, created_at__gt=cutoff).count()
        station_direct_items.append(
            {
                "kind": "direct",
                "id": t.pk,
                "title": t.station.name,
                "subtitle": "Прямой чат",
                "last_text": (t.last_message_text_annot or "").strip(),
                "last_at": t.last_message_at or t.last_message_created_at or t.updated_at,
                "unread": int(unread),
                "url": reverse("cabinet:direct_chat_detail", kwargs={"thread_id": t.pk}),
            }
        )

    # ad direct threads (buyer ↔ seller by ad)
    last_ad_direct_msg_sq = (
        AdDirectMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    ad_direct_threads = (
        AdDirectThread.objects.filter(Q(buyer=u) | Q(seller=u))
        .select_related("ad", "buyer", "seller")
        .annotate(
            last_message_text_annot=Subquery(last_ad_direct_msg_sq.values("text")[:1]),
            last_message_created_at=Subquery(last_ad_direct_msg_sq.values("created_at")[:1]),
        )
        .order_by("-last_message_at", "-updated_at", "-pk")
    )
    ad_items = []
    for t in ad_direct_threads:
        epoch_aware = timezone.make_aware(datetime(1970, 1, 1))
        if t.buyer_id == u.pk:
            cutoff = t.buyer_read_up_to or epoch_aware
            unread = AdDirectMessage.objects.filter(thread=t, sender_id=t.seller_id, created_at__gt=cutoff).count()
            peer = t.seller
            role_fb = "Продавец"
        else:
            cutoff = t.seller_read_up_to or epoch_aware
            unread = AdDirectMessage.objects.filter(thread=t, sender_id=t.buyer_id, created_at__gt=cutoff).count()
            peer = t.buyer
            role_fb = "Покупатель"
        peer_name = user_display_name(peer, fallback=role_fb)
        ad_title = (t.ad.title or "").strip() or f"Объявление #{t.ad_id}"
        ad_items.append(
            {
                "kind": "ad",
                "id": t.pk,
                "title": peer_name,
                "ad_caption": ad_title,
                "subtitle": "",
                "last_text": (t.last_message_text_annot or "").strip(),
                "last_at": t.last_message_at or t.last_message_created_at or t.updated_at,
                "unread": int(unread),
                "url": reverse("cabinet:ad_direct_chat_detail", kwargs={"thread_id": t.pk}),
                "peer_avatar_url": user_avatar_url(peer),
            }
        )

    masters_items = _sort_chat_items_by_last_at(booking_items + station_direct_items)
    all_items = _sort_chat_items_by_last_at(booking_items + station_direct_items + ad_items)
    active_tab = _normalize_chats_tab(request.GET.get("tab"))

    return render(
        request,
        "users/cabinet/chats_unified.html",
        {
            "cabinet_section": "chats",
            "items": all_items,
            "booking_items": booking_items,
            "station_direct_items": station_direct_items,
            "ad_items": ad_items,
            "masters_items": masters_items,
            "active_tab": active_tab,
        },
    )


@login_required
def sto_owner_chats_unified(request):
    """
    Единый список чатов владельца СТО: booking + direct.
    """
    if not _approved_sto(request.user):
        raise Http404
    u = request.user

    # booking rooms (owner side)
    last_booking_msg_sq = (
        BookingMessage.objects.filter(room=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    last_read_sq = ChatRoomLastRead.objects.filter(room=OuterRef("pk"), user=u).values("last_read_at")[:1]
    booking_rooms = (
        ChatRoom.objects.filter(booking__station__owner=u)
        .select_related("booking__client", "booking__station")
        .annotate(
            last_message_text=Subquery(last_booking_msg_sq.values("text")[:1]),
            last_message_at=Subquery(last_booking_msg_sq.values("created_at")[:1]),
            last_read_at=Coalesce(Subquery(last_read_sq), Value(_epoch(), output_field=DateTimeField())),
        )
    )
    booking_items = []
    for r in booking_rooms:
        unread = (
            BookingMessage.objects.filter(room=r)
            .exclude(sender=u)
            .filter(created_at__gt=r.last_read_at)
            .count()
        )
        cli = r.booking.client
        booking_items.append(
            {
                "kind": "booking",
                "id": r.pk,
                "title": user_display_name(cli, fallback=cli.phone),
                "subtitle": f"Запись #{r.booking_id}",
                "last_text": (r.last_message_text or "").strip(),
                "last_at": r.last_message_at,
                "unread": int(unread),
                "url": reverse("sto_owner:booking_chat_detail", kwargs={"room_id": r.pk}),
                "peer_avatar_url": user_avatar_url(cli),
            }
        )

    # direct threads (owner side)
    last_direct_msg_sq = (
        StationDirectMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    direct_threads = (
        StationDirectThread.objects.filter(station__owner=u, owner_archived_at__isnull=True)
        .select_related("station", "client")
        .annotate(
            last_message_text_annot=Subquery(last_direct_msg_sq.values("text")[:1]),
            last_message_created_at=Subquery(last_direct_msg_sq.values("created_at")[:1]),
        )
        .order_by("-last_message_at", "-updated_at", "-pk")
    )
    station_direct_items = []
    for t in direct_threads:
        # unread по owner_read_up_to (как уже используется для бейджа)
        cutoff = t.owner_read_up_to or timezone.make_aware(_epoch().replace(tzinfo=dt_tz.utc))
        unread = StationDirectMessage.objects.filter(thread=t, sender_id=t.client_id, created_at__gt=cutoff).count()
        station_direct_items.append(
            {
                "kind": "direct",
                "id": t.pk,
                "title": user_display_name(t.client, fallback=t.client.phone),
                "subtitle": t.station.name,
                "last_text": (t.last_message_text_annot or "").strip(),
                "last_at": t.last_message_at or t.last_message_created_at or t.updated_at,
                "unread": int(unread),
                "url": reverse("sto_owner:direct_chat_detail", kwargs={"thread_id": t.pk}),
                "peer_avatar_url": user_avatar_url(t.client),
            }
        )

    last_ad_msg_sq = (
        AdDirectMessage.objects.filter(thread=OuterRef("pk"))
        .order_by("-created_at", "-pk")
        .values("text", "created_at")[:1]
    )
    seller_ad_threads = (
        AdDirectThread.objects.filter(seller=u)
        .select_related("ad", "buyer", "seller")
        .annotate(
            last_message_text_annot=Subquery(last_ad_msg_sq.values("text")[:1]),
            last_message_created_at=Subquery(last_ad_msg_sq.values("created_at")[:1]),
        )
        .order_by("-last_message_at", "-updated_at", "-pk")
    )
    epoch_aware = timezone.make_aware(datetime(1970, 1, 1))
    ad_items = []
    for t in seller_ad_threads:
        cutoff = t.seller_read_up_to or epoch_aware
        unread = AdDirectMessage.objects.filter(thread=t, sender_id=t.buyer_id, created_at__gt=cutoff).count()
        peer = t.buyer
        peer_name = user_display_name(peer, fallback="Покупатель")
        ad_title = (t.ad.title or "").strip() or f"Объявление #{t.ad_id}"
        ad_items.append(
            {
                "kind": "ad",
                "id": t.pk,
                "title": peer_name,
                "ad_caption": ad_title,
                "subtitle": "",
                "last_text": (t.last_message_text_annot or "").strip(),
                "last_at": t.last_message_at or t.last_message_created_at or t.updated_at,
                "unread": int(unread),
                "url": reverse("cabinet:ad_direct_chat_detail", kwargs={"thread_id": t.pk}),
                "peer_avatar_url": user_avatar_url(peer),
            }
        )

    masters_items = _sort_chat_items_by_last_at(booking_items + station_direct_items)
    all_items = _sort_chat_items_by_last_at(booking_items + station_direct_items + ad_items)
    active_tab = _normalize_chats_tab(request.GET.get("tab"))

    return render(
        request,
        "sto_owner/chats_unified.html",
        {
            "items": all_items,
            "booking_items": booking_items,
            "station_direct_items": station_direct_items,
            "ad_items": ad_items,
            "masters_items": masters_items,
            "active_tab": active_tab,
        },
    )


@login_required
def cabinet_direct_chat_detail(request, thread_id: int):
    u = request.user
    thread = get_object_or_404(
        StationDirectThread.objects.select_related("station", "station__owner", "client"),
        pk=thread_id,
        client=u,
    )
    StationDirectThread.objects.filter(pk=thread.pk).update(client_read_up_to=timezone.now())
    broadcast_booking_inbox_refresh(u.pk)
    msgs = StationDirectMessage.objects.filter(thread=thread).select_related("sender").order_by("created_at", "pk")
    ws_path = f"/ws/station-direct/{thread.pk}/"
    owner = thread.station.owner
    peer_display = user_display_name(owner, fallback=thread.station.name)
    return render(
        request,
        "users/cabinet/direct_chat_detail.html",
        {
            "cabinet_section": "chats",
            "thread": thread,
            "chat_messages": msgs,
            "chat_ws_path": ws_path,
            "peer_display": peer_display,
            "peer_user_id": int(owner.pk),
            "call_context_kind": "station_direct",
            "call_context_id": int(thread.pk),
        },
    )


@login_required
def cabinet_ad_direct_chat_detail(request, thread_id: int):
    u = request.user
    thread = get_object_or_404(
        AdDirectThread.objects.select_related("ad", "buyer", "seller"),
        pk=thread_id,
    )
    if thread.buyer_id != u.pk and thread.seller_id != u.pk:
        raise Http404

    if thread.buyer_id == u.pk:
        AdDirectThread.objects.filter(pk=thread.pk).update(buyer_read_up_to=timezone.now())
        other_label = "Продавец"
        peer = thread.seller
    else:
        AdDirectThread.objects.filter(pk=thread.pk).update(seller_read_up_to=timezone.now())
        other_label = "Покупатель"
        peer = thread.buyer
    other_display = user_display_name(peer, fallback=other_label)

    from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh

    broadcast_booking_inbox_refresh(u.pk)
    msgs = AdDirectMessage.objects.filter(thread=thread).select_related("sender").order_by("created_at", "pk")
    ws_path = f"/ws/ad-direct/{thread.pk}/"
    ad_detail_url = reverse("classifieds:ad_detail", kwargs={"pk": thread.ad_id})
    return render(
        request,
        "users/cabinet/ad_direct_chat_detail.html",
        {
            "cabinet_section": "chats",
            "thread": thread,
            "chat_messages": msgs,
            "chat_ws_path": ws_path,
            "other_label": other_label,
            "other_display": other_display,
            "ad_detail_url": ad_detail_url,
            "peer_avatar_url": user_avatar_url(peer),
            "peer_user_id": int(peer.pk),
            "call_context_kind": "ad_direct",
            "call_context_id": int(thread.pk),
            "call_ad_id": int(thread.ad_id),
        },
    )


@login_required
@require_POST
def ad_direct_thread_send(request, thread_id: int):
    u = request.user
    wants_json = _wants_json(request)
    text = (request.POST.get("text") or "").strip()
    if not text:
        if wants_json:
            return JsonResponse({"ok": False, "error": "Введите текст."}, status=400)
        messages.warning(request, "Введите текст.")
        raise Http404

    thread = get_object_or_404(AdDirectThread.objects.select_related("buyer", "seller", "ad"), pk=thread_id)
    is_buyer = thread.buyer_id == u.pk
    is_seller = thread.seller_id == u.pk
    if not (is_buyer or is_seller):
        if wants_json:
            return JsonResponse({"ok": False, "error": "Доступ запрещён."}, status=403)
        raise Http404

    try:
        if not allow_message_send(user_id=u.pk):
            if wants_json:
                return JsonResponse({"ok": False, "error": "Слишком часто. Подождите немного."}, status=429)
            messages.warning(request, "Слишком часто. Подождите немного.")
            raise Http404
    except RuntimeError:
        pass

    with transaction.atomic():
        msg = AdDirectMessage(thread=thread, sender=u, text=text)
        msg.full_clean()
        msg.save()
        thread.last_message_at = msg.created_at
        thread.save(update_fields=["last_message_at", "updated_at"])

    payload = {
        "type": "direct.message",
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(f"ad_direct_{thread.pk}", payload)

    from apps.chat.booking_inbox_services import broadcast_booking_inbox_refresh

    broadcast_booking_inbox_refresh(thread.buyer_id)
    broadcast_booking_inbox_refresh(thread.seller_id)

    if wants_json:
        return JsonResponse({"ok": True, "message": _serialize_direct_message(msg)})

    return redirect("cabinet:ad_direct_chat_detail", thread_id=thread.pk)


@login_required
def sto_owner_direct_chat_detail(request, thread_id: int):
    if not _approved_sto(request.user):
        raise Http404
    u = request.user
    thread = get_object_or_404(
        StationDirectThread.objects.select_related("station", "client"),
        pk=thread_id,
        station__owner=u,
    )
    # считаем просмотренным
    StationDirectThread.objects.filter(pk=thread.pk).update(owner_read_up_to=timezone.now())
    broadcast_sto_owner_inbox_refresh(u.pk)

    msgs = StationDirectMessage.objects.filter(thread=thread).select_related("sender").order_by("created_at", "pk")
    ws_path = f"/ws/station-direct/{thread.pk}/"
    peer_display = user_display_name(thread.client, fallback=thread.client.phone)
    return render(
        request,
        "sto_owner/direct_chat_detail.html",
        {
            "thread": thread,
            "chat_messages": msgs,
            "chat_ws_path": ws_path,
            "peer_display": peer_display,
            "peer_user_id": int(thread.client_id),
            "call_context_kind": "station_direct",
            "call_context_id": int(thread.pk),
        },
    )


@login_required
@require_POST
def direct_thread_send(request, thread_id: int):
    """
    Унифицированная отправка для direct-чата по thread_id (для клиента и владельца).
    """
    u = request.user
    wants_json = _wants_json(request)
    text = (request.POST.get("text") or "").strip()
    if not text:
        if wants_json:
            return JsonResponse({"ok": False, "error": "Введите текст."}, status=400)
        messages.warning(request, "Введите текст.")
        raise Http404

    thread = get_object_or_404(
        StationDirectThread.objects.select_related("station", "station__owner", "client"),
        pk=thread_id,
    )
    is_client = thread.client_id == u.pk
    is_owner = thread.station.owner_id == u.pk and _approved_sto(u)
    if not (is_client or is_owner):
        if wants_json:
            return JsonResponse({"ok": False, "error": "Доступ запрещён."}, status=403)
        raise Http404

    try:
        if not allow_message_send(user_id=u.pk):
            if wants_json:
                return JsonResponse({"ok": False, "error": "Слишком часто. Подождите немного."}, status=429)
            messages.warning(request, "Слишком часто. Подождите немного.")
            raise Http404
    except RuntimeError:
        pass

    with transaction.atomic():
        msg = StationDirectMessage(thread=thread, sender=u, text=text)
        msg.full_clean()
        msg.save()
        thread.last_message_at = msg.created_at
        thread.owner_archived_at = None
        thread.save(update_fields=["last_message_at", "updated_at", "owner_archived_at"])

    payload = {"type": "direct.message", "id": msg.pk, "sender_id": msg.sender_id, "text": msg.text, "created_at": msg.created_at.isoformat()}
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(f"station_direct_{thread.pk}", payload)

    # обновляем бейджи
    broadcast_sto_owner_inbox_refresh(thread.station.owner_id)
    broadcast_booking_inbox_refresh(thread.client_id)  # best-effort, чтобы хедер пересчитал

    if wants_json:
        return JsonResponse({"ok": True, "message": _serialize_direct_message(msg)})

    if is_owner:
        return redirect("sto_owner:direct_chat_detail", thread_id=thread.pk)
    return redirect("cabinet:direct_chat_detail", thread_id=thread.pk)

