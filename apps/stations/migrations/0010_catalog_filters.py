# Catalog filters: districts, executor type, amenities, offers

import django.db.models.deletion
from django.db import migrations, models


def seed_districts_and_categories(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    District = apps.get_model("stations", "District")
    ServiceCategory = apps.get_model("stations", "ServiceCategory")
    for name, slug, city in [
        ("Центр", "tsentr", "Владикавказ"),
        ("Иристон", "iriston", "Владикавказ"),
        ("Западный", "zapadnyy", "Владикавказ"),
        ("Москва — пример", "moskva-primer", "Москва"),
    ]:
        District.objects.using(db_alias).get_or_create(slug=slug, defaults={"name": name, "city_label": city})
    cats = [
        ("Замена масла", "zamena-masla"),
        ("Шиномонтаж", "shinomontazh"),
        ("Диагностика", "diagnostika"),
        ("Ремонт ходовой", "remont-hodovoy"),
        ("Электрика", "elektrika"),
        ("Кузовной ремонт", "kuzovnoy-remont"),
        ("Ремонт двигателя", "remont-dvigatelya"),
        ("Кондиционер", "konditsioner"),
        ("Компьютерная диагностика", "komp-diagnostika"),
    ]
    for name, slug in cats:
        if ServiceCategory.objects.using(db_alias).filter(slug=slug).exists():
            continue
        if ServiceCategory.objects.using(db_alias).filter(name=name).exists():
            continue
        ServiceCategory.objects.using(db_alias).create(name=name, slug=slug)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0009_promotion"),
    ]

    operations = [
        migrations.CreateModel(
            name="District",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="Название")),
                ("slug", models.SlugField(max_length=140, unique=True, verbose_name="Слаг")),
                (
                    "city_label",
                    models.CharField(
                        blank=True,
                        help_text="Подпись в интерфейсе, например «Владикавказ».",
                        max_length=120,
                        verbose_name="Город / регион",
                    ),
                ),
            ],
            options={
                "verbose_name": "Район",
                "verbose_name_plural": "Районы",
                "ordering": ["city_label", "name"],
            },
        ),
        migrations.AddField(
            model_name="servicestation",
            name="amenity_cards",
            field=models.BooleanField(default=False, verbose_name="Оплата картой"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="amenity_coffee",
            field=models.BooleanField(default=False, verbose_name="Кофе / чай"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="amenity_legal",
            field=models.BooleanField(default=False, verbose_name="Работа с юрлицами"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="amenity_tow",
            field=models.BooleanField(default=False, verbose_name="Эвакуатор / эвакуация"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="amenity_wifi",
            field=models.BooleanField(default=False, verbose_name="Wi‑Fi для клиентов"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="executor_kind",
            field=models.CharField(
                choices=[("sto", "СТО / автосервис"), ("private", "Частный мастер")],
                db_index=True,
                default="sto",
                max_length=20,
                verbose_name="Тип исполнителя",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="is_open_24_7",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Круглосуточно"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="is_verified",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Плашка «Проверен» в каталоге (модерация вручную).",
                verbose_name="Проверен",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="district",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="stations",
                to="stations.district",
                verbose_name="Район / локация",
            ),
        ),
        migrations.AddIndex(
            model_name="servicestation",
            index=models.Index(fields=["executor_kind", "is_verified"], name="stations_se_executo_2b8f7b_idx"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="amenity_cards",
            field=models.BooleanField(default=False, verbose_name="Оплата картой"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="amenity_coffee",
            field=models.BooleanField(default=False, verbose_name="Кофе / чай"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="amenity_legal",
            field=models.BooleanField(default=False, verbose_name="Работа с юрлицами"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="amenity_tow",
            field=models.BooleanField(default=False, verbose_name="Эвакуатор / эвакуация"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="amenity_wifi",
            field=models.BooleanField(default=False, verbose_name="Wi‑Fi для клиентов"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="executor_kind",
            field=models.CharField(
                choices=[("sto", "СТО / автосервис"), ("private", "Частный мастер")],
                db_index=True,
                default="sto",
                max_length=20,
                verbose_name="Тип исполнителя",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="is_open_24_7",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Круглосуточно"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="is_verified",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Плашка «Проверен» в каталоге (модерация вручную).",
                verbose_name="Проверен",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="district",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="stations.district",
                verbose_name="Район / локация",
            ),
        ),
        migrations.CreateModel(
            name="StationServiceOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_from_rub", models.PositiveIntegerField(verbose_name="Цена от, ₽")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="station_offers",
                        to="stations.servicecategory",
                        verbose_name="Услуга",
                    ),
                ),
                (
                    "station",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_offers",
                        to="stations.servicestation",
                        verbose_name="СТО",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ценовое предложение",
                "verbose_name_plural": "Ценовые предложения",
            },
        ),
        migrations.AddConstraint(
            model_name="stationserviceoffer",
            constraint=models.UniqueConstraint(
                fields=("station", "category"),
                name="stations_stationoffer_station_category_uniq",
            ),
        ),
        migrations.RunPython(seed_districts_and_categories, noop_reverse),
    ]
