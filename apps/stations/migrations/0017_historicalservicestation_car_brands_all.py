from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0016_servicestation_car_brands_all"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalservicestation",
            name="car_brands_all",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Если включено — карточка участвует в каталоге при любом фильтре по марке.",
                verbose_name="Все марки",
            ),
        ),
    ]

