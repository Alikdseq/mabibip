# Generated manually (GDAL not required for schema).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_savedcar_favoritestation"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="sto_moderation_status",
            field=models.CharField(
                "Модерация заявки СТО",
                choices=[
                    ("approved", "Одобрено"),
                    ("pending", "На модерации"),
                    ("rejected", "Отклонено"),
                ],
                db_index=True,
                default="approved",
                help_text=(
                    "Для заявок с сайта — «На модерации» до проверки администратором; "
                    "до одобрения ЛК СТО недоступен. Обычные клиенты и созданные админом "
                    "владельцы — «Одобрено»."
                ),
                max_length=20,
            ),
        ),
    ]
