# Generated manually.

from django.db import migrations, models


def backfill_read_pointers(apps, schema_editor):
    SupportTicket = apps.get_model("support", "SupportTicket")
    for row in SupportTicket.objects.all().only("pk", "updated_at").iterator(chunk_size=500):
        SupportTicket.objects.filter(pk=row.pk).update(
            user_last_read_at=row.updated_at,
            staff_last_read_at=row.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="user_last_read_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Время последнего просмотра переписки пользователем в ЛК.",
                null=True,
                verbose_name="Пользователь прочитал до",
            ),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="staff_last_read_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Время последнего просмотра тикета в ERP.",
                null=True,
                verbose_name="Персонал ERP прочитал до",
            ),
        ),
        migrations.RunPython(backfill_read_pointers, migrations.RunPython.noop),
    ]
