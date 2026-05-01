# Причина отмены записи со стороны СТО (уведомление клиенту)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0007_booking_reminder_2h_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="owner_cancel_reason",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                verbose_name="Причина отмены (СТО)",
            ),
        ),
        migrations.AddField(
            model_name="historicalbooking",
            name="owner_cancel_reason",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                verbose_name="Причина отмены (СТО)",
            ),
        ),
    ]
