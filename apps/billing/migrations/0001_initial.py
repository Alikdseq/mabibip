from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("stations", "0004_f4_billing_blocked_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentProviderCustomer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("yookassa", "ЮKassa")], max_length=20)),
                ("provider_customer_id", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_provider_customers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("yookassa", "ЮKassa")], max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Активна"), ("past_due", "Просрочка оплаты"), ("canceled", "Отменена")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("current_period_end", models.DateField(blank=True, null=True)),
                ("next_charge_at", models.DateTimeField(blank=True, null=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="billing.paymentprovidercustomer",
                    ),
                ),
                (
                    "station",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="stations.servicestation",
                        verbose_name="СТО",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProviderWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("yookassa", "ЮKassa")], max_length=20)),
                ("provider_event_id", models.CharField(max_length=128)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="PaymentIntent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("yookassa", "ЮKassa")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                ("currency", models.CharField(default="RUB", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Создано"),
                            ("succeeded", "Успешно"),
                            ("failed", "Ошибка"),
                            ("canceled", "Отменено"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("idempotency_key", models.CharField(max_length=64)),
                ("provider_payment_id", models.CharField(blank=True, default="", max_length=128)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_intents",
                        to="billing.subscription",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="paymentprovidercustomer",
            constraint=models.UniqueConstraint(
                fields=("provider", "provider_customer_id"),
                name="billing_customer_provider_id_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentprovidercustomer",
            constraint=models.UniqueConstraint(fields=("provider", "user"), name="billing_customer_provider_user_uniq"),
        ),
        migrations.AddConstraint(
            model_name="providerwebhookevent",
            constraint=models.UniqueConstraint(
                fields=("provider", "provider_event_id"),
                name="billing_webhook_event_provider_id_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentintent",
            constraint=models.UniqueConstraint(
                fields=("provider", "idempotency_key"),
                name="billing_intent_provider_idempotency_uniq",
            ),
        ),
    ]

