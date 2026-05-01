# Generated manually.

from django.db import migrations, models
import django.db.models.deletion
from django.contrib.gis.db.models.fields import PointField


class Migration(migrations.Migration):

    dependencies = [
        ("classifieds", "0011_autoshopprofile_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutoShopBranch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=200, verbose_name="Название филиала")),
                ("city_label", models.CharField(blank=True, default="", max_length=120, verbose_name="Город")),
                ("address", models.CharField(blank=True, default="", max_length=500, verbose_name="Адрес")),
                (
                    "location",
                    PointField(
                        blank=True,
                        help_text="Координаты для карты. При включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
                        null=True,
                        srid=4326,
                        verbose_name="Точка на карте (WGS 84)",
                    ),
                ),
                ("contact_phone", models.CharField(blank=True, default="", max_length=32, verbose_name="Телефон")),
                ("work_hours", models.CharField(blank=True, default="", max_length=120, verbose_name="Часы работы")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "shop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branches",
                        to="classifieds.autoshopprofile",
                        verbose_name="Магазин",
                    ),
                ),
            ],
            options={
                "verbose_name": "Филиал автомагазина",
                "verbose_name_plural": "Филиалы автомагазинов",
                "ordering": ["shop_id", "name", "pk"],
            },
        ),
    ]

