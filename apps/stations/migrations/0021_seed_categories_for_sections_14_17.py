from __future__ import annotations

from django.db import migrations


def seed_categories(apps, schema_editor):
    ServiceSection = apps.get_model("stations", "ServiceSection")
    ServiceCategory = apps.get_model("stations", "ServiceCategory")

    def section(slug: str):
        return ServiceSection.objects.filter(slug=slug).first()

    def ensure_cat(*, slug: str, name: str, section_slug: str):
        sec = section(section_slug)
        obj, _ = ServiceCategory.objects.get_or_create(slug=slug, defaults={"name": name})
        updates = []
        if obj.name != name:
            obj.name = name
            updates.append("name")
        # section optional
        if sec and obj.section_id != sec.id:
            obj.section_id = sec.id
            updates.append("section")
        if updates:
            obj.save(update_fields=updates)

    # 14–17 из списокуслуг.txt: создаём базовые "точечные" категории,
    # чтобы их можно было выбрать в списке услуг и чтобы фильтр по разделам не был пустым.
    ensure_cat(slug="evakuator-vyzov", name="Эвакуатор (вызов)", section_slug="tow")
    ensure_cat(slug="avtomagazin", name="Автомагазин (запчасти и автохимия)", section_slug="shop")
    ensure_cat(slug="zamena-masla", name="Замена масла", section_slug="oil")
    ensure_cat(slug="gbo", name="Газовое оборудование (ГБО)", section_slug="lpg")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0020_station_service_sections"),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=noop_reverse),
    ]

