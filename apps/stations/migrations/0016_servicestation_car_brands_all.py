from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0015_savedcar_favoritestation"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicestation",
            name="car_brands_all",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Если включено — карточка участвует в каталоге при любом фильтре по марке.",
                verbose_name="Все марки",
            ),
        ),
    ]
