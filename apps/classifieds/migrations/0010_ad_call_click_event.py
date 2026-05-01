# Generated manually.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("classifieds", "0009_seller_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdCallClickEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "ad_kind",
                    models.CharField(
                        choices=[("part", "Автозапчасть"), ("car", "Автомобиль")],
                        db_index=True,
                        max_length=16,
                        verbose_name="Тип объявления",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "ad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="call_click_events",
                        to="classifieds.ad",
                        verbose_name="Объявление",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classified_ad_call_clicks",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Клик «Позвонить» (объявление)",
                "verbose_name_plural": "Клики «Позвонить» (объявления)",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.AddIndex(
            model_name="adcallclickevent",
            index=models.Index(fields=["ad_kind", "-created_at"], name="clfdc_adcclk_kind_crt"),
        ),
    ]
