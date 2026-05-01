from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0012_user_email_verification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="contact_view_blocked_until",
            field=models.DateTimeField(
                blank=True,
                null=True,
                db_index=True,
                verbose_name="Просмотр контактов заблокирован до",
                help_text="Автоблокировка при превышении лимитов раскрытия телефонов.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_suspicious",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="Подозрительная активность",
                help_text="Флаг антифрода: ограничения на контакты/публикации при подозрительной активности.",
            ),
        ),
    ]

