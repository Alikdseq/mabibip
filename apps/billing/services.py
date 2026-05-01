from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.billing.models import PaymentIntent, PaymentIntentStatus, Subscription, SubscriptionStatus


def apply_successful_payment(*, subscription: Subscription, provider_payment_id: str = "") -> None:
    """
    Успешный платёж продлевает оплаченный период и снимает блокировку.
    Для MVP/каркаса: +30 дней от max(today, current_period_end).
    """
    today = timezone.localdate()
    base = subscription.current_period_end if subscription.current_period_end and subscription.current_period_end > today else today
    new_end = base + timedelta(days=30)

    subscription.current_period_end = new_end
    subscription.next_charge_at = timezone.make_aware(
        timezone.datetime.combine(new_end, timezone.datetime.min.time())
    ) + timedelta(hours=3)  # ~03:00 МСК следующего цикла (упрощённо)
    subscription.reset_failures()
    subscription.save(update_fields=["current_period_end", "next_charge_at", "failed_attempts", "last_failure_at", "status", "updated_at"])

    station = subscription.station
    station.subscription_paid_until = new_end
    station.billing_blocked_at = None
    station.save(update_fields=["subscription_paid_until", "billing_blocked_at"])

    if provider_payment_id:
        PaymentIntent.objects.filter(subscription=subscription, provider_payment_id=provider_payment_id).update(
            status=PaymentIntentStatus.SUCCEEDED
        )


def apply_failed_charge(*, subscription: Subscription) -> None:
    """
    Ошибка списания: увеличиваем счётчик, после 3 попыток блокируем СТО.
    """
    subscription.mark_failure()
    subscription.save(update_fields=["failed_attempts", "last_failure_at", "status", "updated_at"])

    if subscription.failed_attempts >= 3:
        station = subscription.station
        if station.billing_blocked_at is None:
            station.billing_blocked_at = timezone.now()
            station.save(update_fields=["billing_blocked_at"])
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.save(update_fields=["status", "updated_at"])


@transaction.atomic
def ensure_payment_intent(
    *, subscription: Subscription, provider: str, amount, currency: str, idempotency_key: str
) -> PaymentIntent:
    obj, _ = PaymentIntent.objects.get_or_create(
        provider=provider,
        idempotency_key=idempotency_key,
        defaults={
            "subscription": subscription,
            "amount": amount,
            "currency": currency,
            "status": PaymentIntentStatus.PENDING,
        },
    )
    return obj

