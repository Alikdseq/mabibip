from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_user_contact_antifraud_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="business_role_chosen",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="Роль выбрана",
                help_text="True после явного выбора роли пользователем (для OAuth онбординга).",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="contact_phone",
            field=models.CharField(
                blank=True,
                default="",
                db_index=True,
                max_length=32,
                verbose_name="Телефон для связи (E.164)",
                help_text="Контактный номер для связи. Не используется как логин.",
            ),
        ),
    ]

