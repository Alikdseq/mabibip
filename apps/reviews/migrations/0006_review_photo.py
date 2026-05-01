import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0005_reviewreply"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="photo",
            field=models.ImageField(
                blank=True,
                help_text="Необязательно, не более одного файла.",
                null=True,
                upload_to="reviews/%Y/%m/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=("jpg", "jpeg", "png", "webp"),
                        message="Допустимы только изображения JPG, PNG или WEBP.",
                    )
                ],
                verbose_name="Фото",
            ),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="photo",
            field=models.TextField(blank=True, null=True),
        ),
    ]
