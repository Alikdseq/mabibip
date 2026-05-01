# Сценарий СТО: статус «В работе»; один активный слот = pending | confirmed | in_progress

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0005_alter_historicalbooking_options_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="booking",
            name="booking_slot_unique_pending_confirmed",
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("status__in", ["pending", "confirmed", "in_progress"]),
                ),
                fields=("slot",),
                name="booking_slot_unique_active",
            ),
        ),
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидает подтверждения"),
                    ("confirmed", "Подтверждено"),
                    ("in_progress", "В работе"),
                    ("completed", "Завершено"),
                    ("canceled", "Отменено"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Статус",
            ),
        ),
        migrations.AlterField(
            model_name="historicalbooking",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидает подтверждения"),
                    ("confirmed", "Подтверждено"),
                    ("in_progress", "В работе"),
                    ("completed", "Завершено"),
                    ("canceled", "Отменено"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Статус",
            ),
        ),
    ]
