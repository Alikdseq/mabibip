from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import PaymentProvider, Subscription, SubscriptionStatus
from apps.billing.signing import hmac_sha256_hex
from apps.billing.tasks import charge_due_subscriptions
from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC
from apps.stations.models import ServiceStation
from apps.users.models import User


@pytest.fixture(autouse=True)
def _enable_yookassa_integration_flag(settings):
    """Вебхук и боевые сценарии ожидают включённую интеграцию в настройках."""
    settings.YOOKASSA_ENABLED = True


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79994440111",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def station(owner):
    return ServiceStation.objects.create(
        owner=owner,
        name="СТО Billing",
        slug="sto-billing",
        address="ул. Биллинг, 1",
        subscription_plan=SUBSCRIPTION_PLAN_BASIC,
        subscription_paid_until=None,
        is_active=True,
    )


@pytest.fixture
def subscription(db, station):
    return Subscription.objects.create(
        provider=PaymentProvider.YOOKASSA,
        station=station,
        status=SubscriptionStatus.ACTIVE,
        current_period_end=None,
        next_charge_at=timezone.now() - timedelta(minutes=1),
    )


@pytest.mark.django_db
def test_f4_t1_fake_webhook_without_signature_forbidden(settings, subscription):
    settings.YOOKASSA_WEBHOOK_SECRET = "secret"
    payload = {"id": "evt-1", "event": "payment.succeeded", "object": {"metadata": {"station_id": subscription.station_id}}}
    body = json.dumps(payload).encode("utf-8")
    r = Client().post("/billing/webhooks/yookassa/", data=body, content_type="application/json")
    assert r.status_code == 403


@pytest.mark.django_db
def test_f4_t2_webhook_idempotent_no_double_extension(settings, subscription):
    settings.YOOKASSA_WEBHOOK_SECRET = "secret"
    payload = {"id": "evt-42", "event": "payment.succeeded", "object": {"metadata": {"station_id": subscription.station_id}}}
    body = json.dumps(payload).encode("utf-8")
    sig = hmac_sha256_hex(settings.YOOKASSA_WEBHOOK_SECRET, body)

    c = Client()
    r1 = c.post(
        "/billing/webhooks/yookassa/",
        data=body,
        content_type="application/json",
        **{"HTTP_X_WEBHOOK_SIGNATURE": sig},
    )
    assert r1.status_code == 200
    subscription.refresh_from_db()
    first_end = subscription.current_period_end
    assert first_end is not None

    r2 = c.post(
        "/billing/webhooks/yookassa/",
        data=body,
        content_type="application/json",
        **{"HTTP_X_WEBHOOK_SIGNATURE": sig},
    )
    assert r2.status_code == 200
    subscription.refresh_from_db()
    assert subscription.current_period_end == first_end


@pytest.mark.django_db
def test_f4_t3_failed_retries_block_station(subscription):
    # принудительно падаем три раза через monkeypatch apply_successful_payment
    import apps.billing.tasks as tasks_mod

    original = tasks_mod.apply_successful_payment

    def _boom(*args, **kwargs):
        raise RuntimeError("payment failed")

    tasks_mod.apply_successful_payment = _boom
    try:
        for _ in range(3):
            charge_due_subscriptions()
            subscription.refresh_from_db()
            subscription.next_charge_at = timezone.now() - timedelta(minutes=1)
            subscription.save(update_fields=["next_charge_at"])
        station = subscription.station
        station.refresh_from_db()
        assert station.billing_blocked_at is not None
        assert ServiceStation.objects.visible_in_catalog(today=timezone.localdate()).filter(pk=station.pk).exists() is False
    finally:
        tasks_mod.apply_successful_payment = original


@pytest.mark.django_db
def test_yookassa_webhook_disabled_returns_403(settings):
    settings.YOOKASSA_ENABLED = False
    r = Client().post("/billing/webhooks/yookassa/", data=b"{}", content_type="application/json")
    assert r.status_code == 403


def test_yookassa_checkout_info_page_renders():
    r = Client().get(reverse("billing:yookassa_checkout"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "ЮKassa" in body or "YooKassa" in body or "юкасс" in body.lower()

