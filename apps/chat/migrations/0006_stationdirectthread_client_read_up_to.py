from django.db import migrations, models
from django.utils import timezone


def backfill_client_read_up_to(apps, schema_editor):
    StationDirectThread = apps.get_model("chat", "StationDirectThread")
    for t in StationDirectThread.objects.filter(client_read_up_to__isnull=True).iterator():
        t.client_read_up_to = t.last_message_at or timezone.now()
        t.save(update_fields=["client_read_up_to"])


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0005_merge_0004_0003_chatroomlastread"),
    ]

    operations = [
        migrations.AddField(
            model_name="stationdirectthread",
            name="client_read_up_to",
            field=models.DateTimeField(
                blank=True,
                help_text="Сообщения от владельца с временем позже этого момента считаются непрочитанными для клиента.",
                null=True,
                verbose_name="Клиент просмотрел сообщения до",
            ),
        ),
        migrations.RunPython(backfill_client_read_up_to, migrations.RunPython.noop),
    ]

