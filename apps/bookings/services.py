"""Сервисный слой бронирований (фаза 4.2–4.3)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.exceptions import BookingSlotConflictError, SlotNotBookableError
from apps.bookings.models import Booking, TimeSlot
from apps.bookings.redis_holds import delete_slot_hold
from apps.bookings.slot_rules import slot_is_bookable
from apps.users.models import User

logger = logging.getLogger(__name__)

# Сценарий ЛК: клиент отменяет запись не позднее чем за N часов до начала слота.
CLIENT_CANCEL_MIN_HOURS_BEFORE = 2


def booking_slot_start_datetime(booking: Booking):
    """Дата/время начала слота в активной часовой зоне."""
    naive = datetime.combine(booking.slot.date, booking.slot.start_time)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def client_cancel_booking_precheck(booking: Booking, client: User, *, now=None) -> str | None:
    """None — отмена разрешена; иначе текст причины для пользователя."""
    now = now or timezone.now()
    if not getattr(client, "is_authenticated", False) or booking.client_id != client.pk:
        return "Нет доступа к этой записи."
    if booking.status not in (
        BookingStatus.PENDING,
        BookingStatus.CONFIRMED,
        BookingStatus.IN_PROGRESS,
    ):
        return "Эту запись нельзя отменить в текущем статусе."
    start = booking_slot_start_datetime(booking)
    if start - now < timedelta(hours=CLIENT_CANCEL_MIN_HOURS_BEFORE):
        return (
            f"Отмена возможна не позднее чем за {CLIENT_CANCEL_MIN_HOURS_BEFORE} ч. до начала визита."
        )
    return None


def client_cancel_booking(*, booking: Booking, client: User, now=None) -> None:
    """Отмена записи клиентом (после client_cancel_booking_precheck)."""
    msg = client_cancel_booking_precheck(booking, client, now=now)
    if msg:
        raise ValueError(msg)
    booking.status = BookingStatus.CANCELED
    booking.reschedule_proposed_slot_id = None
    booking.reschedule_owner_message = ""
    booking.save(
        update_fields=[
            "status",
            "reschedule_proposed_slot",
            "reschedule_owner_message",
        ]
    )


def expire_unconfirmed_bookings_now(*, now=None) -> int:
    """Переводит pending с истёкшим sto_confirm_deadline в canceled (сценарий: СТО не подтвердило вовремя)."""
    now = now or timezone.now()
    qs = Booking.objects.filter(
        status=BookingStatus.PENDING,
        sto_confirm_deadline__lt=now,
    )
    ids = list(qs.values_list("pk", flat=True))
    if not ids:
        return 0
    with transaction.atomic():
        Booking.objects.filter(pk__in=ids).update(
            status=BookingStatus.CANCELED,
            reschedule_proposed_slot_id=None,
            reschedule_owner_message="",
        )

        def _notify() -> None:
            from apps.bookings.mail import mail_client_booking_auto_canceled

            for bid in ids:
                try:
                    booking = Booking.objects.select_related("client", "station", "slot").get(pk=bid)
                    mail_client_booking_auto_canceled(booking)
                except Exception:
                    logger.exception("mail_client_booking_auto_canceled failed booking_id=%s", bid)

        transaction.on_commit(_notify)
    return len(ids)


def can_booking_transition_to(booking: Booking, new_status: str, actor: User) -> bool:
    """
    Смена статуса владельцем СТО (сценарий: подтвердить → в работе → завершить; отмена на этапах до завершения).
    """
    if not getattr(actor, "is_authenticated", False):
        return False
    if not getattr(actor, "is_sto_owner", False):
        return False
    if getattr(actor, "sto_moderation_status", User.StoModerationStatus.APPROVED) != User.StoModerationStatus.APPROVED:
        return False
    if booking.station.owner_id != actor.pk:
        return False
    cur = booking.status
    if new_status == BookingStatus.CONFIRMED:
        return cur == BookingStatus.PENDING
    if new_status == BookingStatus.CANCELED:
        return cur in (
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.IN_PROGRESS,
        )
    if new_status == BookingStatus.IN_PROGRESS:
        return cur == BookingStatus.CONFIRMED
    if new_status == BookingStatus.COMPLETED:
        return cur == BookingStatus.IN_PROGRESS
    return False


def apply_owner_booking_transition(
    booking: Booking,
    new_status: str,
    actor: User,
    *,
    owner_cancel_reason: str = "",
) -> None:
    """Сохраняет новый статус после проверки can_booking_transition_to."""
    if not can_booking_transition_to(booking, new_status, actor):
        raise Http404
    old_status = booking.status
    reason_clean = (owner_cancel_reason or "").strip()[:500]
    booking.status = new_status
    update_fields = ["status"]
    if new_status == BookingStatus.CANCELED:
        booking.owner_cancel_reason = reason_clean
        update_fields.append("owner_cancel_reason")
        booking.reschedule_proposed_slot_id = None
        booking.reschedule_owner_message = ""
        update_fields.extend(["reschedule_proposed_slot", "reschedule_owner_message"])
    booking.save(update_fields=update_fields)
    bid = booking.pk
    ns = new_status

    def _notify() -> None:
        from apps.bookings import mail as booking_mail

        try:
            b = Booking.objects.select_related("client", "station", "slot").get(pk=bid)
            if ns == BookingStatus.CONFIRMED and old_status == BookingStatus.PENDING:
                booking_mail.mail_client_booking_confirmed(b)
                # pop-up клиенту (персистентно, чтобы не пропустить)
                try:
                    from apps.chat.toast_events import enqueue_user_toast

                    enqueue_user_toast(
                        user_id=b.client_id,
                        kind="client_booking_confirmed",
                        payload={
                            "booking_id": b.pk,
                            "station_name": b.station.name,
                            "slot_summary": booking_reschedule_slot_summary(b.slot),
                        },
                    )
                except Exception:
                    logger.exception("enqueue_user_toast confirmed failed booking_id=%s", bid)
            elif ns == BookingStatus.COMPLETED and old_status == BookingStatus.IN_PROGRESS:
                booking_mail.mail_client_booking_completed(b)
                # realtime-подсказка клиенту: оставить отзыв
                try:
                    from apps.chat.booking_inbox_services import broadcast_review_prompt

                    broadcast_review_prompt(
                        user_id=b.client_id,
                        booking_id=b.pk,
                        station_name=b.station.name,
                    )
                except Exception:
                    logger.exception("broadcast_review_prompt failed booking_id=%s", bid)
            elif ns == BookingStatus.CANCELED and old_status in (
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
                BookingStatus.IN_PROGRESS,
            ):
                booking_mail.mail_client_booking_canceled_by_sto(b)
                # pop-up клиенту об отказе/отмене
                try:
                    from apps.chat.toast_events import enqueue_user_toast

                    enqueue_user_toast(
                        user_id=b.client_id,
                        kind="client_booking_canceled",
                        payload={
                            "booking_id": b.pk,
                            "station_name": b.station.name,
                            "reason": (b.owner_cancel_reason or "").strip(),
                        },
                    )
                except Exception:
                    logger.exception("enqueue_user_toast canceled failed booking_id=%s", bid)
        except Exception:
            logger.exception(
                "client booking mail failed booking_id=%s new_status=%s",
                bid,
                ns,
            )

    transaction.on_commit(_notify)

    # обновляем бейджи у владельца (заявки) после изменения статуса
    def _inbox_refresh() -> None:
        try:
            from apps.chat.inbox_services import broadcast_sto_owner_inbox_refresh

            broadcast_sto_owner_inbox_refresh(actor.pk)
        except Exception:
            logger.exception("sto owner inbox refresh failed booking_id=%s", bid)

    transaction.on_commit(_inbox_refresh)


def _schedule_sto_notification(booking_id: int, request) -> None:
    """Отправка письма после фиксации транзакции (на случай отката до commit)."""

    def _send() -> None:
        from apps.bookings.mail import mail_sto_new_booking

        try:
            booking = Booking.objects.get(pk=booking_id)
            mail_sto_new_booking(booking, request=request)
        except Exception:
            logger.exception("mail_sto_new_booking failed booking_id=%s", booking_id)

    transaction.on_commit(_send)


def create_booking_request(
    *,
    client: User,
    slot_id: int,
    car_info: str,
    contact_phone: str,
    description: str,
    now=None,
    send_notification: bool = True,
    request=None,
) -> Booking:
    """
    Атомарное создание заявки: блокировка слота, проверка доступности, INSERT.
    """
    now = now or timezone.now()
    car_info = (car_info or "").strip()
    contact_phone = (contact_phone or "").strip()
    description = (description or "").strip()

    with transaction.atomic():
        try:
            slot = (
                TimeSlot.objects.select_for_update().select_related("bay__station").get(pk=slot_id)
            )
        except TimeSlot.DoesNotExist:
            logger.info("create_booking_request: slot missing slot_id=%s", slot_id)
            raise SlotNotBookableError from None
        if not slot_is_bookable(slot, now=now, for_user=client):
            raise SlotNotBookableError
        deadline = now + timedelta(hours=1)
        booking = Booking(
            client=client,
            station=slot.bay.station,
            slot=slot,
            car_info=car_info,
            contact_phone=contact_phone,
            description=description,
            status=BookingStatus.PENDING,
            sto_confirm_deadline=deadline,
        )
        try:
            booking.save()
        except IntegrityError as exc:
            logger.warning("booking slot conflict slot_id=%s client_id=%s", slot_id, client.pk)
            raise BookingSlotConflictError from exc
        delete_slot_hold(slot.pk)

    if send_notification:
        _schedule_sto_notification(booking.pk, request)
    # обновляем бейджи у владельца по заявкам
    try:
        from apps.chat.inbox_services import broadcast_sto_owner_inbox_refresh

        broadcast_sto_owner_inbox_refresh(booking.station.owner_id)
    except Exception:
        logger.exception("sto owner inbox refresh failed new booking_id=%s", booking.pk)

    # pop-up владельцу: новая заявка (персистентно)
    def _owner_popup() -> None:
        try:
            from django.urls import reverse

            from apps.chat.toast_events import enqueue_owner_toast

            b = Booking.objects.select_related("station", "slot", "slot__bay").get(pk=booking.pk)
            enqueue_owner_toast(
                owner_user_id=b.station.owner_id,
                kind="owner_new_booking",
                payload={
                    "booking_id": b.pk,
                    "station_name": b.station.name,
                    "slot_summary": booking_reschedule_slot_summary(b.slot),
                    "client_phone": b.contact_phone,
                    "confirm_url": reverse("sto_owner:booking_confirm", kwargs={"pk": b.pk}),
                    "open_url": f"{reverse('sto_owner:dashboard')}?open_booking={b.pk}",
                },
            )
        except Exception:
            logger.exception("enqueue_owner_toast new booking failed booking_id=%s", booking.pk)

    transaction.on_commit(_owner_popup)

    return booking


def booking_reschedule_slot_summary(slot: TimeSlot) -> str:
    return (
        f"{slot.date.strftime('%d.%m.%Y')} "
        f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}, {slot.bay.name}"
    )


def owner_propose_booking_reschedule(
    *,
    booking: Booking,
    actor: User,
    new_slot_id: int,
    owner_message: str = "",
) -> None:
    """СТО предлагает клиенту другое окно (заявка остаётся pending до ответа клиента)."""
    from apps.bookings.slot_rules import slot_is_bookable

    if not getattr(actor, "is_authenticated", False) or booking.station.owner_id != actor.pk:
        raise Http404
    if booking.status != BookingStatus.PENDING:
        raise ValueError("Перенос можно предложить только для новой заявки.")
    try:
        new_slot = TimeSlot.objects.select_related("bay__station").get(pk=int(new_slot_id))
    except (TimeSlot.DoesNotExist, ValueError):
        raise ValueError("Указанное окно не найдено.") from None
    if new_slot.bay.station_id != booking.station_id:
        raise ValueError("Окно должно относиться к вашей станции.")
    if new_slot.pk == booking.slot_id:
        raise ValueError("Выберите другое время, отличное от запроса клиента.")
    msg = (owner_message or "").strip()[:500]
    bid = booking.pk
    new_slot_pk = int(new_slot.pk)

    with transaction.atomic():
        b = Booking.objects.select_for_update().get(pk=bid, station__owner=actor)
        if b.status != BookingStatus.PENDING:
            raise ValueError("Перенос можно предложить только для новой заявки.")
        locked_slot = TimeSlot.objects.select_for_update().select_related("bay__station").get(pk=new_slot_pk)
        if locked_slot.bay.station_id != b.station_id:
            raise ValueError("Окно должно относиться к вашей станции.")
        if locked_slot.pk == b.slot_id:
            raise ValueError("Выберите другое время, отличное от запроса клиента.")
        if not slot_is_bookable(locked_slot, exclude_reschedule_for_booking_id=b.pk):
            raise ValueError("Это время недоступно для записи (занято или закрыто).")
        b.reschedule_proposed_slot = locked_slot
        b.reschedule_owner_message = msg
        b.save(update_fields=["reschedule_proposed_slot", "reschedule_owner_message"])

        def _notify() -> None:
            try:
                from apps.chat.booking_inbox_services import broadcast_reschedule_prompt
                from apps.chat.toast_events import enqueue_user_toast

                b2 = Booking.objects.select_related(
                    "station",
                    "reschedule_proposed_slot",
                    "reschedule_proposed_slot__bay",
                ).get(pk=bid)
                slot2 = b2.reschedule_proposed_slot
                if not slot2:
                    return
                payload = {
                    "booking_id": b2.pk,
                    "station_name": b2.station.name,
                    "slot_summary": booking_reschedule_slot_summary(slot2),
                    "owner_message": b2.reschedule_owner_message or "",
                }
                broadcast_reschedule_prompt(user_id=b2.client_id, **payload)
                enqueue_user_toast(user_id=b2.client_id, kind="client_reschedule_prompt", payload=payload)
            except Exception:
                logger.exception("broadcast_reschedule_prompt failed booking_id=%s", bid)

        transaction.on_commit(_notify)


def client_accept_reschedule(*, booking: Booking, client: User) -> None:
    """Клиент соглашается на предложенное СТО время: перенос слота и авто-подтверждение."""
    from apps.bookings import mail as booking_mail
    from apps.bookings.slot_rules import slot_is_bookable
    from apps.chat.booking_inbox_services import broadcast_sto_reschedule_notice

    if not getattr(client, "is_authenticated", False) or booking.client_id != client.pk:
        raise Http404
    if booking.status != BookingStatus.PENDING or not booking.reschedule_proposed_slot_id:
        raise ValueError("Нет активного предложения переноса.")

    bid = booking.pk

    with transaction.atomic():
        b = Booking.objects.select_for_update().select_related("station", "client").get(pk=bid, client=client)
        if b.status != BookingStatus.PENDING or not b.reschedule_proposed_slot_id:
            raise ValueError("Нет активного предложения переноса.")
        new_slot = TimeSlot.objects.select_for_update().select_related("bay").get(pk=b.reschedule_proposed_slot_id)
        if not slot_is_bookable(new_slot, exclude_reschedule_for_booking_id=b.pk):
            raise ValueError("Это время уже занято. Обновите страницу или откажитесь от предложения.")
        b.slot = new_slot
        b.reschedule_proposed_slot_id = None
        b.reschedule_owner_message = ""
        b.status = BookingStatus.CONFIRMED
        b.save(
            update_fields=[
                "slot",
                "reschedule_proposed_slot",
                "reschedule_owner_message",
                "status",
            ]
        )

        def _notify() -> None:
            try:
                b2 = Booking.objects.select_related("station", "slot", "slot__bay", "client").get(pk=bid)
                booking_mail.mail_client_booking_confirmed(b2)
            except Exception:
                logger.exception("mail after reschedule accept booking_id=%s", bid)
            try:
                b2 = Booking.objects.select_related("station", "slot", "slot__bay").get(pk=bid)
                broadcast_sto_reschedule_notice(
                    owner_user_id=b2.station.owner_id,
                    kind="reschedule_accepted",
                    booking_id=b2.pk,
                    station_slug=b2.station.slug,
                    slot_summary=booking_reschedule_slot_summary(b2.slot),
                    client_phone=b2.contact_phone,
                )
                try:
                    from apps.chat.toast_events import enqueue_owner_toast

                    enqueue_owner_toast(
                        owner_user_id=b2.station.owner_id,
                        kind="owner_reschedule_accepted",
                        payload={
                            "booking_id": b2.pk,
                            "client_phone": b2.contact_phone,
                            "slot_summary": booking_reschedule_slot_summary(b2.slot),
                        },
                    )
                except Exception:
                    logger.exception("enqueue_owner_toast reschedule accepted failed booking_id=%s", bid)
            except Exception:
                logger.exception("broadcast_sto reschedule_accepted failed booking_id=%s", bid)

        transaction.on_commit(_notify)


def client_decline_reschedule(*, booking: Booking, client: User) -> None:
    """Клиент отклоняет перенос; СТО получает уведомление."""
    from django.urls import reverse

    from apps.chat.booking_inbox_services import broadcast_sto_reschedule_notice

    if not getattr(client, "is_authenticated", False) or booking.client_id != client.pk:
        raise Http404
    if not booking.reschedule_proposed_slot_id:
        raise ValueError("Нет активного предложения переноса.")

    bid = booking.pk
    owner_id = booking.station.owner_id
    phone = booking.contact_phone

    with transaction.atomic():
        b = Booking.objects.select_for_update().get(pk=bid, client=client)
        if not b.reschedule_proposed_slot_id:
            raise ValueError("Нет активного предложения переноса.")
        b.reschedule_proposed_slot_id = None
        b.reschedule_owner_message = ""
        b.save(update_fields=["reschedule_proposed_slot", "reschedule_owner_message"])

        def _notify() -> None:
            try:
                b2 = Booking.objects.select_related("station").get(pk=bid)
                try:
                    from apps.chat.models import ChatRoom

                    room, _ = ChatRoom.objects.get_or_create(booking=b2)
                    chat_url = reverse("sto_owner:booking_chat_detail", kwargs={"room_id": room.pk})
                except Exception:
                    chat_url = reverse("sto_owner:booking_chats")
                broadcast_sto_reschedule_notice(
                    owner_user_id=owner_id,
                    kind="reschedule_declined",
                    booking_id=bid,
                    station_slug=b2.station.slug,
                    client_phone=phone,
                    chat_url=chat_url,
                )
                try:
                    from apps.chat.toast_events import enqueue_owner_toast

                    enqueue_owner_toast(
                        owner_user_id=owner_id,
                        kind="owner_reschedule_declined",
                        payload={
                            "booking_id": bid,
                            "client_phone": phone,
                            "chat_url": chat_url,
                        },
                    )
                except Exception:
                    logger.exception("enqueue_owner_toast reschedule declined failed booking_id=%s", bid)
            except Exception:
                logger.exception("broadcast_sto reschedule_declined failed booking_id=%s", bid)

        transaction.on_commit(_notify)
