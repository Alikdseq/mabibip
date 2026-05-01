from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.billing.models import ClassifiedsDeal, PaymentProvider, WalletLedgerEntry
from apps.billing.signing import hmac_sha256_hex
from apps.billing.deal_services import ensure_wallet
from apps.billing.tasks import auto_confirm_and_release_deals, cancel_stale_classifieds_deals
from apps.classifieds.models import Ad, AdKind
from apps.users.models import User


@pytest.fixture(autouse=True)
def _enable_yookassa_flag(settings):
    settings.YOOKASSA_ENABLED = True
    settings.YOOKASSA_WEBHOOK_SECRET = "secret"


@pytest.fixture
def seller(db):
    return User.objects.create_user(phone="+79990000001", password="x", is_phone_verified=True)


@pytest.fixture
def buyer(db):
    return User.objects.create_user(phone="+79990000002", password="x", is_phone_verified=True)


@pytest.fixture
def ad(db, seller):
    return Ad.objects.create(
        owner=seller,
        kind=AdKind.PART,
        title="Тестовая запчасть",
        price=1000,
        city_label="Москва",
        is_published=True,
    )


@pytest.mark.django_db
def test_webhook_payment_succeeded_creates_hold_and_updates_deal(settings, ad, buyer, seller):
    deal = ClassifiedsDeal.objects.create(
        ad=ad,
        buyer=buyer,
        seller=seller,
        amount=Decimal("1000.00"),
        currency="RUB",
        status=ClassifiedsDeal.Status.PAYMENT_PENDING,
        provider=PaymentProvider.YOOKASSA,
    )
    payload = {
        "id": "evt-1",
        "event": "payment.succeeded",
        "object": {"id": "pay-1", "metadata": {"deal_id": str(deal.pk)}},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = hmac_sha256_hex(settings.YOOKASSA_WEBHOOK_SECRET, body)
    r = Client().post(
        "/billing/webhooks/yookassa/",
        data=body,
        content_type="application/json",
        **{"HTTP_X_WEBHOOK_SIGNATURE": sig},
    )
    assert r.status_code == 200

    deal.refresh_from_db()
    assert deal.provider_payment_id == "pay-1"
    assert deal.status == ClassifiedsDeal.Status.WAITING_SHIPMENT
    assert deal.paid_at is not None

    assert WalletLedgerEntry.objects.filter(
        wallet__user_id=seller.pk,
        kind=WalletLedgerEntry.Kind.DEAL_HOLD,
        direction=WalletLedgerEntry.Direction.CREDIT,
        external_id="pay-1",
    ).count() == 1


@pytest.mark.django_db
def test_cancel_stale_deals_task_cancels_unpaid(settings, ad, buyer, seller):
    deal = ClassifiedsDeal.objects.create(
        ad=ad,
        buyer=buyer,
        seller=seller,
        amount=Decimal("1000.00"),
        currency="RUB",
        status=ClassifiedsDeal.Status.PAYMENT_PENDING,
    )
    ClassifiedsDeal.objects.filter(pk=deal.pk).update(created_at=timezone.now() - timedelta(minutes=60))
    settings.DEAL_PAYMENT_TIMEOUT_MINUTES = 30
    n = cancel_stale_classifieds_deals()
    assert n >= 1
    deal.refresh_from_db()
    assert deal.status == ClassifiedsDeal.Status.CANCELED
    assert deal.canceled_at is not None


@pytest.mark.django_db
def test_auto_confirm_task_releases_funds(settings, ad, buyer, seller):
    deal = ClassifiedsDeal.objects.create(
        ad=ad,
        buyer=buyer,
        seller=seller,
        amount=Decimal("1000.00"),
        currency="RUB",
        status=ClassifiedsDeal.Status.SHIPPED,
        provider_payment_id="pay-99",
        auto_confirm_at=timezone.now() - timedelta(minutes=1),
    )
    # имитируем холд
    w = ensure_wallet(seller.pk)
    WalletLedgerEntry.objects.create(
        wallet=w,
        kind=WalletLedgerEntry.Kind.DEAL_HOLD,
        direction=WalletLedgerEntry.Direction.CREDIT,
        amount=deal.amount,
        currency=deal.currency,
        external_id="pay-99",
        payload={"deal_id": deal.pk},
    )

    n = auto_confirm_and_release_deals()
    assert n >= 1
    deal.refresh_from_db()
    assert deal.status == ClassifiedsDeal.Status.RELEASED
    assert deal.buyer_confirmed_at is not None

    assert WalletLedgerEntry.objects.filter(
        wallet=w,
        kind=WalletLedgerEntry.Kind.DEAL_HOLD,
        direction=WalletLedgerEntry.Direction.DEBIT,
        external_id="pay-99",
    ).count() == 1
    assert WalletLedgerEntry.objects.filter(
        wallet=w,
        kind=WalletLedgerEntry.Kind.DEAL_RELEASE,
        direction=WalletLedgerEntry.Direction.CREDIT,
        external_id="pay-99",
    ).count() == 1
