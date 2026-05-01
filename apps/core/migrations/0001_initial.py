from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CityExpansionSignal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("city_label", models.CharField(db_index=True, max_length=120, unique=True, verbose_name="Город")),
                ("seen_count", models.PositiveIntegerField(default=0, verbose_name="Сколько регистраций бизнеса")),
                ("first_seen_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Первое появление")),
                ("last_seen_at", models.DateTimeField(auto_now=True, db_index=True, verbose_name="Последнее появление")),
                ("acknowledged", models.BooleanField(db_index=True, default=False, verbose_name="Админ подтвердил («Отлично»)")),
            ],
            options={
                "verbose_name": "сигнал расширения города",
                "verbose_name_plural": "сигналы расширения городов",
                "ordering": ["acknowledged", "-last_seen_at", "city_label"],
            },
        ),
    ]

