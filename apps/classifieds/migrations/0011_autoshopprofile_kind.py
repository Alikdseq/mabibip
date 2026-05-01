# Generated manually.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classifieds", "0010_ad_call_click_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="autoshopprofile",
            name="kind",
            field=models.CharField(
                choices=[("shop", "Автомагазин"), ("dismantle", "Разборка"), ("dealer", "Автосалон")],
                db_index=True,
                default="shop",
                max_length=16,
                verbose_name="Тип",
            ),
        ),
    ]

