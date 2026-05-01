from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0014_user_oauth_onboarding_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactPhoneChangeRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "old_phone_e164",
                    models.CharField(
                        blank=True, default="", max_length=32, verbose_name="Старый контактный телефон (E.164)"
                    ),
                ),
                ("new_phone_e164", models.CharField(db_index=True, max_length=32, verbose_name="Новый контактный телефон (E.164)")),
                ("reason", models.CharField(blank=True, default="", max_length=500, verbose_name="Причина смены")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "На рассмотрении"), ("approved", "Одобрено"), ("rejected", "Отклонено")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "admin_comment",
                    models.CharField(blank=True, default="", max_length=500, verbose_name="Комментарий администратора"),
                ),
                ("decided_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Решение принято")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создано")),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decided_contact_phone_change_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Решение принял",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contact_phone_change_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "заявка на смену контактного телефона",
                "verbose_name_plural": "заявки на смену контактного телефона",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="contactphonechangerequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "pending")),
                fields=("user",),
                name="users_contact_phone_change_one_pending_per_user",
            ),
        ),
    ]

