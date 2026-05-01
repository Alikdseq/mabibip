from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


def seed_service_sections(apps, schema_editor):
    ServiceSection = apps.get_model("stations", "ServiceSection")
    ServiceCategory = apps.get_model("stations", "ServiceCategory")

    # Финальные разделы (по списокуслуг.txt + уточнение: без "Слесарный ремонт", а разнести на 3).
    sections = [
        ("appearance", "Мойка / детейлинг / химчистка", "bi-stars", 10),
        ("maintenance", "ТО (регламентное обслуживание)", "bi-wrench-adjustable", 20),
        ("diagnostics", "Диагностика", "bi-speedometer2", 30),
        ("suspension", "Ходовая (подвеска)", "bi-truck", 40),
        ("steering", "Рулевое управление", "bi-arrow-left-right", 50),
        ("brakes", "Тормозная система", "bi-exclamation-octagon", 60),
        ("engine", "Ремонт двигателя", "bi-gear-wide-connected", 70),
        ("transmission", "Трансмиссия", "bi-gear", 80),
        ("fuel", "Топливная система", "bi-fuel-pump", 90),
        ("exhaust", "Выхлопная система", "bi-cloud", 100),
        ("electrical", "Электрика и электроника", "bi-lightning-charge", 110),
        ("climate", "Кондиционер и отопитель", "bi-snow", 120),
        ("tires", "Шиномонтаж и колёса", "bi-circle", 130),
        ("bodywork", "Кузовной ремонт", "bi-brush", 140),
        ("roadside", "Помощь на дороге", "bi-cone-striped", 150),
        ("tow", "Эвакуатор", "bi-truck-flatbed", 160),
        ("shop", "Автомагазин", "bi-bag", 170),
        ("oil", "Замена масла", "bi-droplet", 180),
        ("lpg", "Газовое оборудование", "bi-fire", 190),
    ]

    by_slug = {}
    for slug, name, icon, order in sections:
        obj, _ = ServiceSection.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "icon": icon, "sort_order": order},
        )
        # если уже есть — можно аккуратно обновить имя/иконку/порядок на актуальные
        updates = []
        if obj.name != name:
            obj.name = name
            updates.append("name")
        if (obj.icon or "") != (icon or ""):
            obj.icon = icon
            updates.append("icon")
        if obj.sort_order != order:
            obj.sort_order = order
            updates.append("sort_order")
        if updates:
            obj.save(update_fields=updates)
        by_slug[slug] = obj

    # Маппинг существующих SEO/каталог категорий по слагам (не трогаем "точечные" неизвестные).
    slug_to_section = {
        # Уже используемые категории в каталоге/лендингах
        "moyka": "appearance",
        "deteyling": "appearance",
        "himchistka-salona": "appearance",
        "polirovka-kuzova": "appearance",
        "antikor": "appearance",
        "to-i-obsluzhivanie": "maintenance",
        "zamena-masla": "oil",
        "diagnostika": "diagnostics",
        "komp-diagnostika": "diagnostics",
        # ходовая / рулевое / тормоза
        "remont-hodovoy": "suspension",
        "remont-podveski": "suspension",
        "razval-shozhdenie": "suspension",
        "shinomontazh": "tires",
        "remont-gur": "steering",
        # тормоза (есть точечные категории, если заведены)
        "zamena-tormoznyh-kolodok": "brakes",
        "zamena-tormoznyh-diskov": "brakes",
        # двигатель / трансмиссия
        "remont-dvigatelya": "engine",
        "zamen-remnya-grm": "engine",
        "remont-akpp": "transmission",
        # климат / электрика
        "konditsioner": "climate",
        "elektrika": "electrical",
        # кузов
        "kuzovnoy-remont": "bodywork",
        # помощь на дороге
        "evakuator-vyzov": "tow",
    }

    for cat in ServiceCategory.objects.all():
        if cat.section_id:
            continue
        key = slug_to_section.get(cat.slug)
        if key and key in by_slug:
            cat.section_id = by_slug[key].id
            cat.save(update_fields=["section"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0018_servicecategory_landing_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Раздел")),
                ("slug", models.SlugField(db_index=True, max_length=140, unique=True, verbose_name="Слаг")),
                (
                    "icon",
                    models.CharField(
                        blank=True,
                        help_text="Например bi-tools, bi-wrench, bi-brakes. Используется на главной.",
                        max_length=60,
                        verbose_name="Иконка (Bootstrap Icons)",
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="Порядок")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Раздел услуг",
                "verbose_name_plural": "Разделы услуг",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="servicecategory",
            name="section",
            field=models.ForeignKey(
                blank=True,
                help_text="Группа услуг для кнопок/фильтра по разделу. Можно оставить пустым для точечных категорий.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="categories",
                to="stations.servicesection",
                verbose_name="Раздел",
            ),
        ),
        migrations.RunPython(seed_service_sections, reverse_code=noop_reverse),
    ]

