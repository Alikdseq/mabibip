# Generated manually.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_user_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.ImageField(
                blank=True,
                upload_to="users/avatars/%Y/%m/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=("jpg", "jpeg", "png", "webp"),
                        message="Допустимы только изображения JPG, PNG или WEBP.",
                    ),
                ],
                verbose_name="Фото профиля",
            ),
        ),
    ]
