from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from apps.chat.models import chat_attachment_upload_to


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0003_f3_working_hours_slot_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_closed", models.BooleanField(default=False, verbose_name="Закрыта")),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="Закрыта в")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_room",
                        to="bookings.booking",
                        verbose_name="Бронирование",
                    ),
                ),
            ],
            options={"verbose_name": "Чат", "verbose_name_plural": "Чаты"},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(blank=True, default="")),
                ("attachment", models.FileField(blank=True, null=True, upload_to=chat_attachment_upload_to)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_by_client", models.BooleanField(default=False)),
                ("read_by_owner", models.BooleanField(default=False)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="chat.chatroom",
                        verbose_name="Чат",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Сообщение",
                "verbose_name_plural": "Сообщения",
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["room", "created_at"], name="chat_messa_room_id_8a7f96_idx"),
        ),
    ]

