# Напоминание клиенту за ~2 ч до визита (Celery)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0006_booking_in_progress_and_slot_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="reminder_2h_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Напоминание за 2 ч отправлено",
            ),
        ),
        migrations.AddField(
            model_name="historicalbooking",
            name="reminder_2h_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Напоминание за 2 ч отправлено",
            ),
        ),
    ]
