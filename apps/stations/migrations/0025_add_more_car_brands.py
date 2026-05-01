from django.db import migrations


NEW_BRANDS = [
    ("changan", "Changan", "changan", 40),
    ("chery", "Chery", "chery", 41),
    ("citroen", "Citroën", "citroen", 42),
    ("dodge", "Dodge", "dodge", 43),
    ("exeed", "Exeed", "exeed", 44),
    ("gaz", "GAZ", "gaz", 45),
    ("haval", "Haval", "haval", 46),
    ("infiniti", "Infiniti", "infiniti", 47),
    ("jeep", "Jeep", "jeep", 48),
    ("land-rover", "Land Rover", "land-rover", 49),
    ("porsche", "Porsche", "porsche", 50),
    ("subaru", "Subaru", "subaru", 51),
    ("tank", "Tank", "tank", 52),
    ("volvo", "Volvo", "volvo", 53),
]


def seed_more_brands(apps, schema_editor):
    CarBrand = apps.get_model("stations", "CarBrand")
    for slug, name, sprite_key, order in NEW_BRANDS:
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
        ("stations", "0024_alter_historicalservicestation_parent_station"),
    ]

    operations = [
        migrations.RunPython(seed_more_brands, migrations.RunPython.noop),
    ]

