from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.billing.models import (
    ClassifiedsDeal,
    PaymentProvider,
    ProviderWebhookEvent,
    Subscription,
    Wallet,
    WalletLedgerEntry,
)
from apps.billing.services import apply_successful_payment
from apps.billing.signing import constant_time_equals, hmac_sha256_hex

logger = logging.getLogger(__name__)


def _get_event_id(payload: dict) -> str | None:
    for k in ("event_id", "id", "eventId"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _get_metadata(payload: dict) -> dict:
    obj = payload.get("object", {})
    if isinstance(obj, dict):
        meta = obj.get("metadata", {})
        if isinstance(meta, dict):
            return meta
    return {}


def _ensure_wallet(user_id: int) -> Wallet:
    obj, _ = Wallet.objects.get_or_create(user_id=int(user_id))
    return obj


def _wallet_entry_idempotent(
    *,
    wallet: Wallet,
    kind: str,
    direction: str,
    amount,
    currency: str,
    external_id: str,
    payload: dict,
) -> WalletLedgerEntry:
    entry, _ = WalletLedgerEntry.objects.get_or_create(
        wallet=wallet,
        kind=kind,
        direction=direction,
        external_id=external_id or "",
        defaults={
            "amount": amount,
            "currency": currency,
            "payload": payload or {},
        },
    )
    return entry


@csrf_exempt
def yookassa_webhook(request: HttpRequest) -> HttpResponse:
    """
    Вебхук провайдера. Требования:
    - проверка подписи (секрет только из env)
    - идемпотентность по provider_event_id
    """
    if not getattr(settings, "YOOKASSA_ENABLED", False):
        return JsonResponse({"detail": "YooKassa integration is disabled"}, status=403)

    secret = getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "").strip()
    if not secret:
        return JsonResponse({"detail": "Webhook secret not configured"}, status=500)

    raw = request.body or b""
    sig = request.headers.get("X-Webhook-Signature", "")
    expected = hmac_sha256_hex(secret, raw)
    if not constant_time_equals(sig, expected):
        return JsonResponse({"detail": "Invalid signature"}, status=403)

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    event_id = _get_event_id(payload)
    if not event_id:
        return JsonResponse({"detail": "Missing event id"}, status=400)

    _, created = ProviderWebhookEvent.objects.get_or_create(
        provider=PaymentProvider.YOOKASSA,
        provider_event_id=event_id,
        defaults={"payload": payload},
    )
    if not created:
        return JsonResponse({"status": "ok", "idempotent": True})

    meta = _get_metadata(payload)

    event_type = payload.get("event", payload.get("type", ""))
    provider_payment_id = str(payload.get("object", {}).get("id", "") or "")

    # --- Classifieds safe deals (pseudo-escrow) ---
    deal_id = meta.get("deal_id")
    if deal_id:
        try:
            deal_id_int = int(deal_id)
        except (TypeError, ValueError):
            deal_id_int = None
        if deal_id_int:
            try:
                deal = ClassifiedsDeal.objects.select_related("seller").get(pk=deal_id_int)
            except ClassifiedsDeal.DoesNotExist:
                deal = None
            if deal:
                if event_type in ("payment.succeeded", "payment_succeeded", "succeeded"):
                    if provider_payment_id:
                        if deal.provider_payment_id and deal.provider_payment_id != provider_payment_id:
                            logger.warning(
                                "yookassa_webhook: deal payment_id mismatch deal_id=%s existing=%s incoming=%s",
                                deal.pk,
                                deal.provider_payment_id,
                                provider_payment_id,
                            )
                            return JsonResponse({"status": "ok"})
                        if not deal.provider_payment_id:
                            deal.provider_payment_id = provider_payment_id
                    deal.provider_payload = payload
                    if deal.status in {ClassifiedsDeal.Status.CREATED, ClassifiedsDeal.Status.PAYMENT_PENDING}:
                        deal.status = ClassifiedsDeal.Status.FUNDS_HELD
                        deal.paid_at = timezone.now()
                        # после оплаты сразу ждём отправку/встречу
                        deal.status = ClassifiedsDeal.Status.WAITING_SHIPMENT
                    deal.save(update_fields=["provider_payment_id", "provider_payload", "status", "paid_at"])

                    # Холд на кошельке продавца (идемпотентно по provider_payment_id).
                    if provider_payment_id:
                        w = _ensure_wallet(deal.seller_id)
                        _wallet_entry_idempotent(
                            wallet=w,
                            kind=WalletLedgerEntry.Kind.DEAL_HOLD,
                            direction=WalletLedgerEntry.Direction.CREDIT,
                            amount=deal.amount,
                            currency=deal.currency,
                            external_id=provider_payment_id,
                            payload={"deal_id": deal.pk},
                        )
                elif event_type in ("payment.canceled", "payment_canceled", "canceled"):
                    if deal.status in {ClassifiedsDeal.Status.CREATED, ClassifiedsDeal.Status.PAYMENT_PENDING}:
                        deal.status = ClassifiedsDeal.Status.CANCELED
                        deal.canceled_at = timezone.now()
                        deal.provider_payload = payload
                        deal.save(update_fields=["status", "canceled_at", "provider_payload"])

        return JsonResponse({"status": "ok"})

    # --- Existing case: station subscriptions ---
    station_id = meta.get("station_id")
    try:
        station_id_int = int(station_id)
    except (TypeError, ValueError):
        logger.info("yookassa_webhook: missing metadata (station_id/deal_id) event_id=%s", event_id)
        return JsonResponse({"status": "ok"})

    try:
        subscription = Subscription.objects.select_related("station").get(station_id=station_id_int)
    except Subscription.DoesNotExist:
        return JsonResponse({"status": "ok"})

    if event_type in ("payment.succeeded", "payment_succeeded", "succeeded"):
        apply_successful_payment(subscription=subscription, provider_payment_id=provider_payment_id)

    return JsonResponse({"status": "ok"})

