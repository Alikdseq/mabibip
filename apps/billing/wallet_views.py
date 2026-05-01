from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.billing.forms import WithdrawalRequestForm
from apps.billing.models import WalletLedgerEntry, WithdrawalRequest
from apps.billing.wallet_services import ensure_wallet_for_user, wallet_balances


@login_required
@require_http_methods(["GET"])
def wallet_home(request):
    wallet = ensure_wallet_for_user(request.user.pk)
    balances = wallet_balances(wallet)
    entries = wallet.entries.all()[:200]
    return render(
        request,
        "billing/wallet_home.html",
        {
            "wallet": wallet,
            "balances": balances,
            "entries": entries,
            "cabinet_section": "wallet",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def withdrawal_request_create(request):
    wallet = ensure_wallet_for_user(request.user.pk)
    balances = wallet_balances(wallet)
    form = WithdrawalRequestForm(request.POST or None, max_amount=balances["available"])
    if request.method == "POST" and form.is_valid():
        obj = WithdrawalRequest.objects.create(
            wallet=wallet,
            amount=form.cleaned_data["amount"],
            currency="RUB",
            payout_details=form.cleaned_data["payout_details"],
            reason=form.cleaned_data.get("reason") or "",
        )
        WalletLedgerEntry.objects.create(
            wallet=wallet,
            kind=WalletLedgerEntry.Kind.WITHDRAWAL_REQUEST,
            direction=WalletLedgerEntry.Direction.DEBIT,
            amount=obj.amount,
            currency=obj.currency,
            external_id=f"withdrawal-request-{obj.pk}",
            payload={"withdrawal_request_id": obj.pk},
        )
        messages.success(request, "Заявка на вывод отправлена и будет рассмотрена администратором.")
        return redirect(reverse("billing:wallet_home"))

    return render(
        request,
        "billing/withdrawal_request_form.html",
        {"form": form, "balances": balances, "cabinet_section": "wallet"},
    )

