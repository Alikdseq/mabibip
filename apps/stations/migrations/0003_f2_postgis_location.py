import django.contrib.gis.db.models.fields
from django.db import migrations


def create_postgis_extension(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def add_gist_location(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS stations_se_location_gist "
            "ON stations_servicestation USING GIST (location);"
        )


def drop_gist_location(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS stations_se_location_gist")


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0002_phase8_help_text"),
    ]

    operations = [
        migrations.RunPython(create_postgis_extension, migrations.RunPython.noop),
        migrations.AddField(
            model_name="servicestation",
            name="location",
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True,
                help_text="Координаты для геопоиска. Можно задать вручную; при включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
                null=True,
                srid=4326,
                verbose_name="Точка на карте (WGS 84)",
            ),
        ),
        migrations.RunPython(add_gist_location, drop_gist_location),
    ]
