from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0005_f7_history"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Название")),
                ("slug", models.SlugField(max_length=140, unique=True, verbose_name="Слаг")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Категория услуг",
                "verbose_name_plural": "Категории услуг",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="servicestation",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="stations", to="stations.servicecategory", verbose_name="Категории услуг"),
        ),
    ]

