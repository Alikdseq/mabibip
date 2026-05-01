from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0003_f2_postgis_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicestation",
            name="billing_blocked_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Если заполнено — СТО скрыта из каталога и не принимает новые заявки (фаза F4).",
                null=True,
                verbose_name="Заблокировано биллингом",
            ),
        ),
    ]

