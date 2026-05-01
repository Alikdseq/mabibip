from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0017_historicalservicestation_car_brands_all"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicecategory",
            name="landing_faq",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Список объектов {"q": "вопрос", "a": "ответ"} для блока FAQ и разметки FAQPage.',
                verbose_name="FAQ для лендинга (JSON)",
            ),
        ),
        migrations.AddField(
            model_name="servicecategory",
            name="landing_lead",
            field=models.TextField(
                blank=True,
                help_text="Уникальный абзац для SEO (plain text). Пусто — только общий шаблон.",
                verbose_name="Лид-текст для лендинга /uslugi/",
            ),
        ),
    ]
