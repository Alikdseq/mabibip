# Generated manually (local makemigrations may require GDAL).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classifieds", "0007_favoritead"),
    ]

    operations = [
        migrations.AddField(
            model_name="ad",
            name="view_count",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Счётчик показов карточки; один зачёт не чаще одного раза за сессию браузера.",
                verbose_name="Просмотры",
            ),
        ),
    ]
