from __future__ import annotations

import secrets
from datetime import timedelta

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.calls.livekit_tokens import LiveKitNotConfigured, issue_room_token
from apps.calls.models import Call, CallContextKind, CallStatus
from apps.calls.realtime import send_to_user
from apps.calls.settings import calls_settings
from apps.users.onboarding_access import ensure_completed_profile_api

logger = logging.getLogger(__name__)


def _user_display(u) -> str:
    name = (getattr(u, "get_full_name", lambda: "")() or "").strip()
    if name:
        return name
    return (getattr(u, "phone", "") or getattr(u, "email", "") or f"User #{u.pk}").strip()


def _avatar_url(u) -> str:
    try:
        if getattr(u, "avatar", None) and getattr(u.avatar, "url", None):
            return str(u.avatar.url)
    except Exception:
        pass
    return ""


def _calls_enabled_or_403():
    if not calls_settings().enabled:
        return Response({"ok": False, "error": "Функция звонков отключена."}, status=403)
    return None


class CallsInitiateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "calls_initiate"

    def post(self, request):
        blocked = ensure_completed_profile_api(request)
        if blocked is not None:
            return blocked

        blocked = _calls_enabled_or_403()
        if blocked is not None:
            return blocked

        User = get_user_model()
        receiver_id = int(request.data.get("receiver_user_id") or 0)
        if not receiver_id:
            return Response({"ok": False, "error": "receiver_user_id обязателен."}, status=400)
        if int(receiver_id) == int(request.user.pk):
            return Response({"ok": False, "error": "Нельзя звонить самому себе."}, status=400)

        receiver = User.objects.filter(pk=receiver_id, is_active=True).first()
        if not receiver:
            return Response({"ok": False, "error": "Пользователь не найден."}, status=404)

        ad_id = request.data.get("ad_id")
        context_kind = str(request.data.get("context_kind") or CallContextKind.NONE).strip() or CallContextKind.NONE
        context_id = request.data.get("context_id")
        try:
            context_id_int = int(context_id) if context_id is not None else None
        except (TypeError, ValueError):
            context_id_int = None

        ad = None
        if ad_id:
            try:
                from apps.classifieds.models import Ad

                ad = Ad.objects.filter(pk=int(ad_id), is_published=True).select_related("owner", "shop").first()
            except Exception:
                ad = None

        now = timezone.now()
        ring_cutoff = now - timedelta(seconds=int(calls_settings().ring_timeout_sec))

        # Дедупликация: запрещаем новый звонок, если у любого участника есть активный звонок.
        active_q = Call.objects.filter(status__in=[CallStatus.INITIATED, CallStatus.RINGING, CallStatus.ACTIVE]).filter(
            caller_id__in=[request.user.pk, receiver.pk]
        ) | Call.objects.filter(
            status__in=[CallStatus.INITIATED, CallStatus.RINGING, CallStatus.ACTIVE]
        ).filter(
            receiver_id__in=[request.user.pk, receiver.pk]
        )
        if active_q.exists():
            return Response({"ok": False, "error": "У одного из участников уже есть активный звонок."}, status=409)

        room_name = f"call_{int(request.user.pk)}_{int(receiver.pk)}_{secrets.token_hex(4)}"

        try:
            caller_token = issue_room_token(user=request.user, room_name=room_name)
            receiver_token = issue_room_token(user=receiver, room_name=room_name)
        except LiveKitNotConfigured as e:
            logger.info("calls initiate rejected: livekit not configured user_id=%s", request.user.pk)
            return Response({"ok": False, "error": str(e)}, status=503)

        with transaction.atomic():
            call = Call.objects.create(
                room_name=room_name,
                caller=request.user,
                receiver=receiver,
                status=CallStatus.RINGING,
                context_kind=context_kind if context_kind in dict(CallContextKind.choices) else CallContextKind.NONE,
                context_id=context_id_int,
                ad=ad,
            )

        logger.info(
            "calls initiate ok call_id=%s caller=%s receiver=%s context=%s/%s ad_id=%s",
            call.pk,
            request.user.pk,
            receiver.pk,
            call.context_kind,
            call.context_id,
            call.ad_id,
        )

        # Сообщение получателю по WS: входящий звонок.
        send_to_user(
            user_id=receiver.pk,
            payload={
                "type": "call.incoming",
                "call_id": int(call.pk),
                "room_name": room_name,
                "token": receiver_token,
                "livekit_url": calls_settings().livekit_url,
                "ring_timeout_sec": int(calls_settings().ring_timeout_sec),
                "caller": {
                    "id": int(request.user.pk),
                    "name": _user_display(request.user),
                    "avatar": _avatar_url(request.user),
                },
                "context": {
                    "kind": call.context_kind,
                    "id": int(call.context_id) if call.context_id else None,
                    "ad_id": int(ad.pk) if ad else None,
                    "ad_title": str(ad.title) if ad else None,
                },
            },
        )

        return Response(
            {
                "ok": True,
                "call_id": int(call.pk),
                "room_name": room_name,
                "token": caller_token,
                "status": "ringing",
                "livekit_url": calls_settings().livekit_url,
                "ring_timeout_sec": int(calls_settings().ring_timeout_sec),
            }
        )


class CallsActionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "calls_action"

    def post(self, request):
        blocked = ensure_completed_profile_api(request)
        if blocked is not None:
            return blocked

        blocked = _calls_enabled_or_403()
        if blocked is not None:
            return blocked

        call_id = int(request.data.get("call_id") or 0)
        if not call_id:
            return Response({"ok": False, "error": "call_id обязателен."}, status=400)
        action = str(request.data.get("action") or "").strip().lower()
        if action not in ("accept", "decline", "end"):
            return Response({"ok": False, "error": "action должен быть accept/decline/end."}, status=400)

        call = Call.objects.select_related("caller", "receiver", "ad").filter(pk=call_id).first()
        if not call:
            return Response({"ok": False, "error": "Звонок не найден."}, status=404)

        u = request.user
        is_caller = int(call.caller_id) == int(u.pk)
        is_receiver = int(call.receiver_id) == int(u.pk)
        if not (is_caller or is_receiver):
            return Response({"ok": False, "error": "Нет доступа к звонку."}, status=403)

        now = timezone.now()
        ring_timeout = int(calls_settings().ring_timeout_sec)
        ring_deadline = (call.created_at or now) + timedelta(seconds=ring_timeout)

        with transaction.atomic():
            call.refresh_from_db()

            # Таймаут «не ответили»: фиксируем при любом действии после дедлайна.
            if call.status == CallStatus.RINGING and now > ring_deadline and action != "accept":
                call.mark_ended(status=CallStatus.MISSED)
                call.save(update_fields=["status", "ended_at", "updated_at"])
            if action == "accept":
                if not is_receiver:
                    return Response({"ok": False, "error": "Принять звонок может только получатель."}, status=403)
                if call.status != CallStatus.RINGING:
                    return Response({"ok": False, "error": "Звонок нельзя принять в текущем статусе."}, status=409)
                if now > ring_deadline:
                    call.mark_ended(status=CallStatus.MISSED)
                    call.save(update_fields=["status", "ended_at", "updated_at"])
                    send_to_user(
                        user_id=call.caller_id,
                        payload={"type": "call.timeout", "call_id": int(call.pk)},
                    )
                    return Response({"ok": False, "error": "Звонок пропущен (таймаут)."}, status=409)
                call.mark_active()
                call.save(update_fields=["status", "started_at", "updated_at"])
                logger.info("calls accepted call_id=%s by=%s", call.pk, request.user.pk)

            elif action == "decline":
                if not is_receiver:
                    return Response({"ok": False, "error": "Отклонить звонок может только получатель."}, status=403)
                if call.status not in (CallStatus.RINGING, CallStatus.INITIATED):
                    return Response({"ok": False, "error": "Звонок нельзя отклонить в текущем статусе."}, status=409)
                call.mark_ended(status=CallStatus.DECLINED)
                call.save(update_fields=["status", "ended_at", "updated_at"])
                logger.info("calls declined call_id=%s by=%s", call.pk, request.user.pk)

            elif action == "end":
                if call.status not in (CallStatus.ACTIVE, CallStatus.RINGING, CallStatus.INITIATED):
                    # идемпотентность: end можно вызывать повторно
                    return Response({"ok": True})
                call.mark_ended(status=CallStatus.COMPLETED if call.status == CallStatus.ACTIVE else CallStatus.MISSED)
                call.save(update_fields=["status", "ended_at", "updated_at"])
                logger.info("calls ended call_id=%s by=%s", call.pk, request.user.pk)

        # WS уведомления (вне транзакции)
        if action == "accept":
            send_to_user(
                user_id=call.caller_id,
                payload={
                    "type": "call.accepted",
                    "call_id": int(call.pk),
                    "room_name": call.room_name,
                },
            )
            send_to_user(
                user_id=call.receiver_id,
                payload={
                    "type": "call.active",
                    "call_id": int(call.pk),
                    "room_name": call.room_name,
                },
            )
        elif action == "decline":
            send_to_user(user_id=call.caller_id, payload={"type": "call.declined", "call_id": int(call.pk)})
            send_to_user(user_id=call.receiver_id, payload={"type": "call.declined", "call_id": int(call.pk)})
        elif action == "end":
            send_to_user(user_id=call.caller_id, payload={"type": "call.ended", "call_id": int(call.pk)})
            send_to_user(user_id=call.receiver_id, payload={"type": "call.ended", "call_id": int(call.pk)})

        return Response({"ok": True, "status": call.status})

