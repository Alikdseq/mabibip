# Generated manually for reschedule proposal flow

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0009_timeslot_manual_block_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="reschedule_owner_message",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Текст от мастера/СТО: почему предлагается другое время.",
                max_length=500,
                verbose_name="Сообщение клиенту при переносе",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="reschedule_proposed_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="bookings.timeslot",
                verbose_name="Предложенный слот (перенос)",
            ),
        ),
        migrations.AddField(
            model_name="historicalbooking",
            name="reschedule_owner_message",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Текст от мастера/СТО: почему предлагается другое время.",
                max_length=500,
                verbose_name="Сообщение клиенту при переносе",
            ),
        ),
        migrations.AddField(
            model_name="historicalbooking",
            name="reschedule_proposed_slot",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="bookings.timeslot",
                verbose_name="Предложенный слот (перенос)",
            ),
        ),
    ]
