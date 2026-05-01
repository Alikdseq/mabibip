from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_user_sto_moderation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="sto_chat_auto_prune_inactive",
            field=models.BooleanField(
                default=True,
                help_text="Если включено, переписки без сообщений более 3 суток удаляются автоматически.",
                verbose_name="Автоудаление неактивных чатов (3 дня)",
            ),
        ),
    ]
