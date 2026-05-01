from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.billing.models import Wallet, WalletLedgerEntry


def ensure_wallet_for_user(user_id: int) -> Wallet:
    obj, _ = Wallet.objects.get_or_create(user_id=int(user_id))
    return obj


def _sum_signed(qs) -> Decimal:
    credit = qs.filter(direction=WalletLedgerEntry.Direction.CREDIT).aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
    debit = qs.filter(direction=WalletLedgerEntry.Direction.DEBIT).aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
    return Decimal(credit) - Decimal(debit)


def _sum_debit(qs) -> Decimal:
    debit = qs.filter(direction=WalletLedgerEntry.Direction.DEBIT).aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
    return Decimal(debit)


def wallet_balances(wallet: Wallet) -> dict:
    """
    Возвращает агрегированные балансы кошелька.
    - held: деньги на холде по сделкам
    - available: доступно к выводу (после релиза) минус подтверждённые выводы
    """
    entries = WalletLedgerEntry.objects.filter(wallet=wallet)
    held = _sum_signed(entries.filter(kind=WalletLedgerEntry.Kind.DEAL_HOLD))
    released = _sum_signed(entries.filter(kind=WalletLedgerEntry.Kind.DEAL_RELEASE))
    withdrawn = _sum_debit(entries.filter(kind=WalletLedgerEntry.Kind.WITHDRAWAL_APPROVED))
    available = released - withdrawn
    return {"held": held, "available": available}

