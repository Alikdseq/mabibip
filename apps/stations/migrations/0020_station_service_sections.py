from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0019_service_sections"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicestation",
            name="service_sections",
            field=models.ManyToManyField(
                blank=True,
                help_text="Если выбрать разделы, станция будет попадать в фильтр каталога по разделу даже без точечных категорий.",
                related_name="stations",
                to="stations.servicesection",
                verbose_name="Разделы услуг (быстрый выбор)",
            ),
        ),
    ]

