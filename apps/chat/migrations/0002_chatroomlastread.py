from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatRoomLastRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_read_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="last_reads",
                        to="chat.chatroom",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_last_reads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Последнее прочтение чата",
                "verbose_name_plural": "Последние прочтения чатов",
            },
        ),
        migrations.AddConstraint(
            model_name="chatroomlastread",
            constraint=models.UniqueConstraint(fields=("room", "user"), name="chat_room_last_read_unique"),
        ),
        migrations.AddIndex(
            model_name="chatroomlastread",
            index=models.Index(fields=["room", "user"], name="chat_last_r_room_id_7c6a9b_idx"),
        ),
        migrations.AddIndex(
            model_name="chatroomlastread",
            index=models.Index(fields=["user", "-last_read_at"], name="chat_last_r_user_id_8a5bb2_idx"),
        ),
    ]

