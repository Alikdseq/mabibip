from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentProvider(models.TextChoices):
    YOOKASSA = "yookassa", "ЮKassa"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Активна"
    PAST_DUE = "past_due", "Просрочка оплаты"
    CANCELED = "canceled", "Отменена"


class PaymentIntentStatus(models.TextChoices):
    PENDING = "pending", "Создано"
    SUCCEEDED = "succeeded", "Успешно"
    FAILED = "failed", "Ошибка"
    CANCELED = "canceled", "Отменено"


class PaymentProviderCustomer(models.Model):
    """
    Клиент у провайдера (например YooKassa customer).
    Не хранить PAN/CVV; только provider_id и метаданные безопасные.
    """

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_provider_customers",
    )
    provider_customer_id = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_customer_id"],
                name="billing_customer_provider_id_uniq",
            ),
            models.UniqueConstraint(
                fields=["provider", "user"],
                name="billing_customer_provider_user_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_customer_id}"


class Subscription(models.Model):
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    station = models.OneToOneField(
        "stations.ServiceStation",
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name="СТО",
    )
    customer = models.ForeignKey(
        PaymentProviderCustomer,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    current_period_end = models.DateField(null=True, blank=True)
    next_charge_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Subscription({self.station_id}) {self.status}"

    def mark_failure(self) -> None:
        self.failed_attempts += 1
        self.last_failure_at = timezone.now()
        if self.failed_attempts > 0:
            self.status = SubscriptionStatus.PAST_DUE

    def reset_failures(self) -> None:
        self.failed_attempts = 0
        self.last_failure_at = None
        self.status = SubscriptionStatus.ACTIVE


class PaymentIntent(models.Model):
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payment_intents")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="RUB")
    status = models.CharField(max_length=20, choices=PaymentIntentStatus.choices, default=PaymentIntentStatus.PENDING)
    idempotency_key = models.CharField(max_length=64)
    provider_payment_id = models.CharField(max_length=128, blank=True, default="")
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "idempotency_key"],
                name="billing_intent_provider_idempotency_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"Intent({self.provider}) {self.status} {self.amount} {self.currency}"


class ProviderWebhookEvent(models.Model):
    """
    Идемпотентность вебхуков: один provider_event_id обрабатываем ровно 1 раз.
    """

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    provider_event_id = models.CharField(max_length=128)
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"],
                name="billing_webhook_event_provider_id_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"Webhook({self.provider}) {self.provider_event_id}"


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Кошелёк"
        verbose_name_plural = "Кошельки"

    def __str__(self) -> str:
        return f"Wallet({self.user_id})"


class WalletLedgerEntry(models.Model):
    class Direction(models.TextChoices):
        CREDIT = "credit", "Поступление"
        DEBIT = "debit", "Списание"

    class Kind(models.TextChoices):
        DEAL_HOLD = "deal_hold", "Холд по сделке"
        DEAL_RELEASE = "deal_release", "Релиз по сделке"
        REFUND = "refund", "Возврат покупателю"
        WITHDRAWAL_REQUEST = "withdrawal_request", "Заявка на вывод"
        WITHDRAWAL_APPROVED = "withdrawal_approved", "Вывод подтверждён"
        MANUAL_ADJUST = "manual_adjust", "Ручная корректировка"
        FEE = "fee", "Комиссия"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="entries", verbose_name="Кошелёк")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    kind = models.CharField(max_length=40, choices=Kind.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="RUB")
    external_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Идентификатор у провайдера/внешней системы для идемпотентности (например provider_payment_id).",
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись кошелька"
        verbose_name_plural = "Записи кошелька"
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "kind", "direction", "external_id"],
                condition=~models.Q(external_id=""),
                name="billing_wallet_entry_wallet_kind_external_uniq",
            )
        ]
        ordering = ["-created_at", "-pk"]

    def signed_amount(self) -> Decimal:
        return self.amount if self.direction == self.Direction.CREDIT else -self.amount

    def __str__(self) -> str:
        return f"{self.wallet_id} {self.kind} {self.direction} {self.amount} {self.currency}"


class ClassifiedsDeal(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Создана"
        PAYMENT_PENDING = "payment_pending", "Ожидает оплаты"
        FUNDS_HELD = "funds_held", "Оплачено (холд)"
        WAITING_SHIPMENT = "waiting_shipment", "Ожидает отправки/встречи"
        SHIPPED = "shipped", "Отправлено"
        BUYER_CONFIRMED = "buyer_confirmed", "Получено покупателем"
        RELEASED = "released", "Завершено (средства доступны продавцу)"
        CANCELED = "canceled", "Отменено"
        REFUND_PENDING = "refund_pending", "Возврат в обработке"
        REFUNDED = "refunded", "Возвращено"

    class DeliveryKind(models.TextChoices):
        MEETUP = "meetup", "Самовывоз/встреча"
        DELIVERY = "delivery", "Доставка"

    ad = models.ForeignKey("classifieds.Ad", on_delete=models.PROTECT, related_name="deals", verbose_name="Объявление")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="classifieds_deals_buyer",
        verbose_name="Покупатель",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="classifieds_deals_seller",
        verbose_name="Продавец",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="RUB")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED, db_index=True)
    delivery_kind = models.CharField(max_length=16, choices=DeliveryKind.choices, default=DeliveryKind.MEETUP)

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices, default=PaymentProvider.YOOKASSA)
    provider_payment_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    provider_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)
    seller_marked_shipped_at = models.DateTimeField(null=True, blank=True)
    buyer_confirmed_at = models.DateTimeField(null=True, blank=True)
    auto_confirm_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Сделка по объявлению"
        verbose_name_plural = "Сделки по объявлениям"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_payment_id"],
                condition=~models.Q(provider_payment_id=""),
                name="billing_classifieds_deal_provider_payment_uniq",
            )
        ]
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"Deal({self.pk}) {self.status}"


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        APPROVED = "approved", "Подтверждено"
        REJECTED = "rejected", "Отклонено"
        PAID = "paid", "Выплачено"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="withdrawal_requests", verbose_name="Кошелёк")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="RUB")
    payout_details = models.CharField(
        "Реквизиты для выплаты",
        max_length=200,
        help_text="Например: карта ****1234 / СБП / банк. MVP: текст, т.к. вывод ручной.",
    )
    reason = models.CharField("Комментарий", max_length=300, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    admin_comment = models.CharField("Комментарий администратора", max_length=300, blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Заявка на вывод"
        verbose_name_plural = "Заявки на вывод"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"Withdrawal({self.pk}) {self.status} {self.amount} {self.currency}"

