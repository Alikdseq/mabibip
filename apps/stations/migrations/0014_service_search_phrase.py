# Словарь «живых» запросов → категории услуг (умные подсказки).

import django.db.models.deletion
from django.db import migrations, models


def add_trgm_index_if_postgres(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # Без расширения pg_trgm класс gin_trgm_ops недоступен (ошибка в Docker/Postgres).
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS stations_servicesearchphrase_trgm "
        "ON stations_servicesearchphrase USING gin (phrase_normalized gin_trgm_ops);"
    )


def drop_trgm_index_if_postgres(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS stations_servicesearchphrase_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0013_sync_model_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceSearchPhrase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phrase", models.CharField(max_length=500, verbose_name="Фраза")),
                (
                    "phrase_normalized",
                    models.CharField(db_index=True, max_length=500, verbose_name="Нормализованная фраза"),
                ),
                (
                    "weight",
                    models.PositiveSmallIntegerField(
                        default=5,
                        help_text="Выше — важнее при совпадении с запросом.",
                        verbose_name="Вес (1–10)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="search_phrases",
                        to="stations.servicecategory",
                        verbose_name="Категория услуг",
                    ),
                ),
            ],
            options={
                "verbose_name": "Поисковая фраза",
                "verbose_name_plural": "Поисковые фразы",
            },
        ),
        migrations.AddConstraint(
            model_name="servicesearchphrase",
            constraint=models.UniqueConstraint(
                fields=("phrase_normalized", "category"),
                name="stations_searchphrase_norm_cat_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="servicesearchphrase",
            index=models.Index(fields=["phrase_normalized", "weight"], name="stations_se_phrase__f8950c_idx"),
        ),
        migrations.RunPython(add_trgm_index_if_postgres, drop_trgm_index_if_postgres),
    ]
