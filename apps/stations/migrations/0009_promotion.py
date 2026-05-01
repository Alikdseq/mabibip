# Generated manually for homepage promotions

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0008_alter_servicestation_subscription_plan_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="Заголовок")),
                ("summary", models.TextField(blank=True, verbose_name="Кратко")),
                ("link_url", models.URLField(blank=True, help_text="Если задана, кнопка ведёт сюда; иначе — на карточку СТО (если выбрана).", verbose_name="Внешняя ссылка")),
                ("discount_percent", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Скидка, %")),
                ("valid_until", models.DateField(blank=True, null=True, verbose_name="Действует до")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "station",
                    models.ForeignKey(
                        blank=True,
                        help_text="Пусто — общая акция платформы (ссылка на каталог или link_url).",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotions",
                        to="stations.servicestation",
                        verbose_name="СТО",
                    ),
                ),
            ],
            options={
                "verbose_name": "Акция",
                "verbose_name_plural": "Акции",
                "ordering": ["sort_order", "-created_at"],
            },
        ),
    ]
