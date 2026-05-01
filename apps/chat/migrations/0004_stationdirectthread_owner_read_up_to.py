from django.db import migrations, models
from django.utils import timezone


def backfill_owner_read_up_to(apps, schema_editor):
    StationDirectThread = apps.get_model("chat", "StationDirectThread")
    for t in StationDirectThread.objects.filter(owner_read_up_to__isnull=True).iterator():
        t.owner_read_up_to = t.last_message_at or timezone.now()
        t.save(update_fields=["owner_read_up_to"])


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_station_direct_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="stationdirectthread",
            name="owner_read_up_to",
            field=models.DateTimeField(
                blank=True,
                help_text="Сообщения от клиента с временем позже этого момента считаются непрочитанными для бейджа.",
                null=True,
                verbose_name="Владелец просмотрел сообщения до",
            ),
        ),
        migrations.RunPython(backfill_owner_read_up_to, migrations.RunPython.noop),
    ]
