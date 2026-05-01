from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("classifieds", "0015_contacts_antifraud_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="ad",
            name="moderation_status",
            field=models.CharField(
                choices=[("ok", "OK"), ("pending", "На проверке"), ("hidden", "Скрыто")],
                db_index=True,
                default="ok",
                max_length=20,
                verbose_name="Модерация",
            ),
        ),
        migrations.AddField(
            model_name="ad",
            name="moderation_reason",
            field=models.CharField(blank=True, default="", max_length=300, verbose_name="Причина модерации"),
        ),
    ]

