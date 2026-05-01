# Комментарий владельца при ручном закрытии слота (календарь СТО)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0008_booking_owner_cancel_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeslot",
            name="manual_block_note",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
                verbose_name="Причина закрытия (для себя)",
                help_text="Например: обед, запчасти. Не видно клиентам.",
            ),
        ),
    ]
