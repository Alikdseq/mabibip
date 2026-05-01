"""Чаты клиент ↔ станция (без записи): панель на карточке и список у владельца."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from apps.chat.inbox_services import (
    broadcast_sto_owner_inbox_refresh,
    mark_direct_threads_read_for_owner,
)
from apps.chat.models import StationDirectMessage, StationDirectThread
from apps.chat.rate_limit import allow_message_send
from apps.stations.models import ServiceStation
from apps.users.models import User


def _station_public(slug: str) -> ServiceStation:
    st = get_object_or_404(
        ServiceStation.objects.filter(is_active=True).select_related("owner"),
        slug=slug,
    )
    # Мастер автосервиса: чат всегда ведём в автосервис-родитель.
    parent = getattr(st, "parent_station", None)
    return parent or st


def _wants_json(request) -> bool:
    accept = request.headers.get("Accept") or ""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in accept


def station_chat_panel(request, slug):
    station = _station_public(slug)
    thread = None
    msgs = []
    ws_path = ""
    if request.user.is_authenticated:
        if station.owner_id != request.user.pk:
            thread, _ = StationDirectThread.objects.get_or_create(
                station=station,
                client=request.user,
                defaults={"owner_read_up_to": timezone.now(), "client_read_up_to": timezone.now()},
            )
            msgs = list(
                StationDirectMessage.objects.filter(thread=thread)
                .select_related("sender")
                .order_by("created_at", "pk")
            )
            if thread:
                ws_path = f"/ws/station-direct/{thread.pk}/"
    return render(
        request,
        "stations/partials/station_chat_panel.html",
        {
            "station": station,
            "thread": thread,
            "direct_messages": msgs,
            "chat_ws_path": ws_path,
        },
    )


def _serialize_direct_message(msg: StationDirectMessage) -> dict:
    return {
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
        "created_at_display": date_format(timezone.localtime(msg.created_at), format="d.m.Y H:i"),
    }


@login_required
@require_POST
def station_chat_send(request, slug):
    station = _station_public(slug)
    wants_json = _wants_json(request)
    text = (request.POST.get("text") or "").strip()

    if not text:
        if wants_json:
            return JsonResponse({"ok": False, "error": "Введите текст сообщения."}, status=400)
        messages.warning(request, "Введите текст сообщения.")
        return redirect(reverse("stations:detail", kwargs={"slug": slug}) + "#station-chat")

    if station.owner_id == request.user.pk:
        if wants_json:
            return JsonResponse(
                {"ok": False, "error": "Ответы — в разделе «Чаты» в кабинете бизнеса."},
                status=403,
            )
        messages.info(request, "Ответы — в разделе «Чаты» в кабинете бизнеса.")
        return redirect(reverse("stations:detail", kwargs={"slug": slug}) + "#station-chat")

    try:
        if not allow_message_send(user_id=request.user.pk):
            if wants_json:
                return JsonResponse(
                    {"ok": False, "error": "Слишком часто. Подождите немного."},
                    status=429,
                )
            messages.warning(request, "Слишком часто. Подождите немного.")
            return redirect(reverse("stations:detail", kwargs={"slug": slug}) + "#station-chat")
    except RuntimeError:
        pass

    with transaction.atomic():
        thread, _ = StationDirectThread.objects.select_for_update().get_or_create(
            station=station,
            client=request.user,
            defaults={"owner_read_up_to": timezone.now(), "client_read_up_to": timezone.now()},
        )
        msg = StationDirectMessage(thread=thread, sender=request.user, text=text)
        msg.full_clean()
        msg.save()
        thread.last_message_at = msg.created_at
        thread.owner_archived_at = None
        thread.save(update_fields=["last_message_at", "updated_at", "owner_archived_at"])

    payload = {
        "type": "direct.message",
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(f"station_direct_{thread.pk}", payload)

    broadcast_sto_owner_inbox_refresh(station.owner_id)

    if wants_json:
        return JsonResponse({"ok": True, "message": _serialize_direct_message(msg)})

    next_url = request.POST.get("next") or reverse("stations:detail", kwargs={"slug": slug})
    return redirect(next_url + ("#station-chat" if "#" not in next_url else ""))


def _approved_sto(user) -> bool:
    return (
        user.is_authenticated
        and getattr(user, "is_sto_owner", False)
        and user.sto_moderation_status == User.StoModerationStatus.APPROVED
    )


@login_required
def sto_owner_chat_list(request):
    if not _approved_sto(request.user):
        raise Http404

    mark_direct_threads_read_for_owner(request.user)
    broadcast_sto_owner_inbox_refresh(request.user.pk)

    qs = (
        StationDirectThread.objects.filter(station__owner=request.user, owner_archived_at__isnull=True)
        .select_related("station", "client")
        .order_by("-last_message_at", "-updated_at", "-pk")
    )
    prune_enabled = getattr(request.user, "sto_chat_auto_prune_inactive", True)
    return render(
        request,
        "sto_owner/direct_chat_list.html",
        {"threads": qs, "prune_enabled": prune_enabled},
    )


@login_required
@require_POST
def sto_owner_chat_settings(request):
    if not _approved_sto(request.user):
        raise Http404
    u = request.user
    u.sto_chat_auto_prune_inactive = request.POST.get("sto_chat_auto_prune_inactive") == "on"
    u.save(update_fields=["sto_chat_auto_prune_inactive"])
    messages.success(request, "Настройки сохранены.")
    return redirect(reverse("sto_owner:chats") + "?tab=masters")


@login_required
@require_POST
def sto_owner_chat_bulk_delete(request):
    if not _approved_sto(request.user):
        raise Http404
    ids = request.POST.getlist("thread_ids")
    if not ids:
        messages.warning(request, "Отметьте хотя бы один чат.")
        return redirect(reverse("sto_owner:chats") + "?tab=masters")
    tid_list = [int(x) for x in ids if str(x).strip().isdigit()]
    deleted, _ = StationDirectThread.objects.filter(
        pk__in=tid_list,
        station__owner=request.user,
    ).delete()
    messages.success(request, f"Удалено переписок: {deleted}.")
    broadcast_sto_owner_inbox_refresh(request.user.pk)
    return redirect(reverse("sto_owner:chats") + "?tab=masters")


@login_required
@require_POST
def sto_owner_chat_reply(request):
    if not _approved_sto(request.user):
        raise Http404
    wants_json = _wants_json(request)
    raw_id = request.POST.get("thread_id")
    text = (request.POST.get("text") or "").strip()

    if not raw_id or not str(raw_id).isdigit():
        if wants_json:
            return JsonResponse({"ok": False, "error": "Не указан диалог."}, status=400)
        messages.error(request, "Не указан диалог.")
        return redirect(reverse("sto_owner:chats") + "?tab=masters")
    if not text:
        if wants_json:
            return JsonResponse({"ok": False, "error": "Введите текст."}, status=400)
        messages.warning(request, "Введите текст.")
        return redirect(reverse("sto_owner:chats") + "?tab=masters")

    thread = get_object_or_404(
        StationDirectThread.objects.select_related("station"),
        pk=int(raw_id),
        station__owner=request.user,
    )

    try:
        if not allow_message_send(user_id=request.user.pk):
            if wants_json:
                return JsonResponse(
                    {"ok": False, "error": "Слишком часто. Подождите немного."},
                    status=429,
                )
            messages.warning(request, "Слишком часто. Подождите немного.")
            return redirect(reverse("sto_owner:chats") + "?tab=masters")
    except RuntimeError:
        pass

    with transaction.atomic():
        msg = StationDirectMessage(thread=thread, sender=request.user, text=text)
        msg.full_clean()
        msg.save()
        thread.last_message_at = msg.created_at
        thread.owner_archived_at = None
        thread.save(update_fields=["last_message_at", "updated_at", "owner_archived_at"])

    payload = {
        "type": "direct.message",
        "id": msg.pk,
        "sender_id": msg.sender_id,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(f"station_direct_{thread.pk}", payload)

    broadcast_sto_owner_inbox_refresh(request.user.pk)

    if wants_json:
        return JsonResponse({"ok": True, "message": _serialize_direct_message(msg)})

    messages.success(request, "Сообщение отправлено.")
    return redirect(reverse("sto_owner:chats") + "?tab=masters")
