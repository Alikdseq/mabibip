# Car brands: фильтр каталога по марке + быстрый выбор на главной/в каталоге

from django.db import migrations, models


POPULAR = [
    ("lada", "LADA", "lada", 1),
    ("audi", "Audi", "audi", 2),
    ("bmw", "BMW", "bmw", 3),
    ("ford", "Ford", "ford", 4),
    ("hyundai", "Hyundai", "hyundai", 5),
    ("kia", "KIA", "kia", 6),
    ("mercedes-benz", "Mercedes-Benz", "mercedes", 7),
    ("nissan", "Nissan", "nissan", 8),
    ("toyota", "Toyota", "toyota", 9),
    ("volkswagen", "Volkswagen", "vw", 10),
]

MORE = [
    ("renault", "Renault", "renault", 20),
    ("skoda", "Skoda", "skoda", 21),
    ("chevrolet", "Chevrolet", "chevrolet", 22),
    ("mazda", "Mazda", "mazda", 23),
    ("mitsubishi", "Mitsubishi", "mitsubishi", 24),
    ("opel", "Opel", "opel", 25),
    ("peugeot", "Peugeot", "peugeot", 26),
    ("honda", "Honda", "honda", 27),
    ("lexus", "Lexus", "lexus", 28),
    ("geely", "Geely", "geely", 29),
]


def seed_brands(apps, schema_editor):
    CarBrand = apps.get_model("stations", "CarBrand")
    for slug, name, sprite_key, order in POPULAR:
        CarBrand.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sprite_key": sprite_key,
                "sort_order": order,
                "is_popular": True,
            },
        )
    for slug, name, sprite_key, order in MORE:
        CarBrand.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sprite_key": sprite_key,
                "sort_order": order,
                "is_popular": False,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0011_station_detail_profile_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarBrand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True, verbose_name="Марка")),
                ("slug", models.SlugField(db_index=True, max_length=80, unique=True, verbose_name="Слаг")),
                (
                    "sprite_key",
                    models.CharField(
                        blank=True,
                        help_text="ID символа в static/pm-brand-sprite.svg (например: bmw, audi).",
                        max_length=60,
                        verbose_name="Ключ логотипа (SVG sprite)",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="Порядок")),
                (
                    "is_popular",
                    models.BooleanField(db_index=True, default=False, verbose_name="Популярная (для главной)"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Марка авто",
                "verbose_name_plural": "Марки авто",
                "ordering": ["-is_popular", "sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="servicestation",
            name="car_brands",
            field=models.ManyToManyField(
                blank=True,
                related_name="stations",
                to="stations.carbrand",
                verbose_name="Марки авто (с которыми работает)",
            ),
        ),
        migrations.RunPython(seed_brands, migrations.RunPython.noop),
    ]

