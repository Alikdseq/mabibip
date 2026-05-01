from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.billing.models import Subscription, SubscriptionStatus
from apps.billing.services import apply_failed_charge, apply_successful_payment
from apps.billing.models import ClassifiedsDeal
from apps.billing.deal_services import mark_buyer_confirmed, release_deal_funds

logger = logging.getLogger(__name__)


@shared_task(name="apps.billing.tasks.charge_due_subscriptions")
def charge_due_subscriptions() -> int:
    """
    Фаза F4.1.4: списание подписок в дату next_charge_at.
    Каркас без реального провайдера: если подписка активна и next_charge_at наступил — считаем «успешно».
    Реальная интеграция подключается через адаптер провайдера (ЮKassa/Тинькофф).
    """
    now = timezone.now()
    qs = Subscription.objects.select_related("station").filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE],
        next_charge_at__isnull=False,
        next_charge_at__lte=now,
    )
    processed = 0
    for sub in qs:
        processed += 1
        try:
            # TODO(F4): заменить на реальный вызов ЮKassa и обработку статусов/ретраев.
            apply_successful_payment(subscription=sub)
        except Exception:
            logger.exception("charge_due_subscriptions failed sub_id=%s", sub.pk)
            apply_failed_charge(subscription=sub)
            # ретраи: следующая попытка через сутки, максимум 3
            if sub.failed_attempts < 3:
                sub.next_charge_at = now + timedelta(days=1)
                sub.save(update_fields=["next_charge_at", "updated_at"])
    return processed


@shared_task(name="apps.billing.tasks.cancel_stale_classifieds_deals")
def cancel_stale_classifieds_deals() -> int:
    """
    Авто-отмена неоплаченных сделок: если платёж не пришёл за N минут — отменяем.
    """
    minutes = int(getattr(settings, "DEAL_PAYMENT_TIMEOUT_MINUTES", 30))
    cutoff = timezone.now() - timedelta(minutes=minutes)
    qs = ClassifiedsDeal.objects.filter(
        status__in=[ClassifiedsDeal.Status.CREATED, ClassifiedsDeal.Status.PAYMENT_PENDING],
        created_at__lte=cutoff,
        paid_at__isnull=True,
    )
    updated = qs.update(status=ClassifiedsDeal.Status.CANCELED, canceled_at=timezone.now())
    return int(updated)


@shared_task(name="apps.billing.tasks.auto_confirm_and_release_deals")
def auto_confirm_and_release_deals() -> int:
    """
    Автоподтверждение получения после таймаута + релиз средств продавцу.
    """
    now = timezone.now()
    qs = ClassifiedsDeal.objects.filter(
        status=ClassifiedsDeal.Status.SHIPPED,
        auto_confirm_at__isnull=False,
        auto_confirm_at__lte=now,
    ).only("id", "seller_id", "amount", "currency", "provider_payment_id", "status", "buyer_confirmed_at")
    processed = 0
    for deal in qs:
        processed += 1
        try:
            mark_buyer_confirmed(deal=deal)
            ext = (deal.provider_payment_id or "").strip() or f"deal-{deal.pk}"
            release_deal_funds(deal=deal, external_id=ext)
        except Exception:
            logger.exception("auto_confirm_and_release_deals failed deal_id=%s", deal.pk)
    return processed

