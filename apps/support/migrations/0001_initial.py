# Generated manually.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(blank=True, default="", max_length=200, verbose_name="Тема")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Открыт"),
                            ("in_progress", "В работе"),
                            ("resolved", "Решён"),
                            ("closed", "Закрыт"),
                        ],
                        db_index=True,
                        default="open",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_tickets",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Обращение в поддержку",
                "verbose_name_plural": "Обращения в поддержку",
                "ordering": ["-updated_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="SupportMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(verbose_name="Текст")),
                ("is_staff_reply", models.BooleanField(db_index=True, default=False, verbose_name="Ответ поддержки")),
                ("is_system_auto", models.BooleanField(db_index=True, default=False, verbose_name="Авто-сообщение")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        help_text="Пусто — системное сообщение.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="support_messages",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Автор",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="support.supportticket",
                        verbose_name="Обращение",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сообщение поддержки",
                "verbose_name_plural": "Сообщения поддержки",
                "ordering": ["created_at", "pk"],
            },
        ),
    ]
