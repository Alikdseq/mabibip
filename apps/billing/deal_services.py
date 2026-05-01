from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.billing.models import ClassifiedsDeal, Wallet, WalletLedgerEntry


def ensure_wallet(user_id: int) -> Wallet:
    obj, _ = Wallet.objects.get_or_create(user_id=int(user_id))
    return obj


def ledger_idempotent(
    *,
    wallet: Wallet,
    kind: str,
    direction: str,
    amount: Decimal,
    currency: str,
    external_id: str,
    payload: dict,
) -> WalletLedgerEntry:
    obj, _ = WalletLedgerEntry.objects.get_or_create(
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
    return obj


@transaction.atomic
def release_deal_funds(*, deal: ClassifiedsDeal, external_id: str) -> None:
    """
    Перевод средств из «холда» в «доступно» на кошельке продавца.
    Идемпотентно по external_id.
    """
    w = ensure_wallet(deal.seller_id)
    # Уменьшаем холд
    ledger_idempotent(
        wallet=w,
        kind=WalletLedgerEntry.Kind.DEAL_HOLD,
        direction=WalletLedgerEntry.Direction.DEBIT,
        amount=deal.amount,
        currency=deal.currency,
        external_id=external_id,
        payload={"deal_id": deal.pk, "op": "release"},
    )
    # Увеличиваем доступный баланс
    ledger_idempotent(
        wallet=w,
        kind=WalletLedgerEntry.Kind.DEAL_RELEASE,
        direction=WalletLedgerEntry.Direction.CREDIT,
        amount=deal.amount,
        currency=deal.currency,
        external_id=external_id,
        payload={"deal_id": deal.pk, "op": "release"},
    )

    if deal.status != ClassifiedsDeal.Status.RELEASED:
        deal.status = ClassifiedsDeal.Status.RELEASED
        deal.save(update_fields=["status"])


@transaction.atomic
def mark_buyer_confirmed(*, deal: ClassifiedsDeal) -> None:
    if not deal.buyer_confirmed_at:
        deal.buyer_confirmed_at = timezone.now()
    if deal.status != ClassifiedsDeal.Status.BUYER_CONFIRMED:
        deal.status = ClassifiedsDeal.Status.BUYER_CONFIRMED
    deal.save(update_fields=["buyer_confirmed_at", "status"])

