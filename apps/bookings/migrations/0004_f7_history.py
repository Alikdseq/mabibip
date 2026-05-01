from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_f3_working_hours_slot_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalBooking",
            fields=[
                ("history_id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id", models.BigIntegerField(db_index=True, verbose_name="ID")),
                ("car_info", models.CharField(max_length=100, verbose_name="Авто (госномер / марка)")),
                ("contact_phone", models.CharField(max_length=20, verbose_name="Телефон для связи")),
                ("description", models.TextField(verbose_name="Описание проблемы")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает подтверждения"),
                            ("confirmed", "Подтверждено"),
                            ("completed", "Завершено"),
                            ("canceled", "Отменено"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("sto_confirm_deadline", models.DateTimeField(blank=True, help_text="Истечение ожидания подтверждения СТО (создание + 1 ч).", null=True, verbose_name="Подтвердить до")),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("history_date", models.DateTimeField()),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(max_length=1)),
                (
                    "client",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Клиент"),
                ),
                (
                    "slot",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to="bookings.timeslot", verbose_name="Слот"),
                ),
                (
                    "station",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to="stations.servicestation", verbose_name="СТО"),
                ),
                (
                    "history_user",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "historical Бронь",
                "verbose_name_plural": "historical Брони",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
        ),
    ]

