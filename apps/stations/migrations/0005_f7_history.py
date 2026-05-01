from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0004_f4_billing_blocked_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalServiceStation",
            fields=[
                ("history_id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id", models.BigIntegerField(db_index=True, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("slug", models.SlugField(db_index=True, max_length=220, verbose_name="Слаг")),
                ("address", models.CharField(max_length=500, verbose_name="Адрес")),
                (
                    "location",
                    gis_models.PointField(
                        blank=True,
                        help_text="Координаты для геопоиска. Можно задать вручную; при включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
                        null=True,
                        srid=4326,
                        verbose_name="Точка на карте (WGS 84)",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                (
                    "subscription_plan",
                    models.CharField(
                        choices=[("free", "Free"), ("basic", "Basic")],
                        default="basic",
                        max_length=20,
                        verbose_name="Тариф",
                    ),
                ),
                ("subscription_paid_until", models.DateField(blank=True, null=True, verbose_name="Подписка оплачена до")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("billing_blocked_at", models.DateTimeField(blank=True, null=True, verbose_name="Заблокировано биллингом")),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("history_date", models.DateTimeField()),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(max_length=1)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Владелец",
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "historical СТО",
                "verbose_name_plural": "historical СТО",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
        ),
    ]

