from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_rename_chat_messa_room_id_8a7f96_idx_chat_messag_room_id_5feac5_idx_and_more"),
        ("stations", "0016_servicestation_car_brands_all"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StationDirectThread",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_message_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner_archived_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Не показывать в списке чатов у СТО (сообщения удаляются вместе с потоком при удалении).",
                        null=True,
                        verbose_name="Скрыто владельцем",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="station_direct_threads",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Клиент",
                    ),
                ),
                (
                    "station",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="direct_threads",
                        to="stations.servicestation",
                        verbose_name="Станция",
                    ),
                ),
            ],
            options={
                "verbose_name": "Чат со станцией",
                "verbose_name_plural": "Чаты со станциями",
            },
        ),
        migrations.AddConstraint(
            model_name="stationdirectthread",
            constraint=models.UniqueConstraint(
                fields=("station", "client"), name="station_direct_thread_unique"
            ),
        ),
        migrations.AddIndex(
            model_name="stationdirectthread",
            index=models.Index(fields=["station", "-last_message_at"], name="chat_stadirec_station_1b6782_idx"),
        ),
        migrations.AddIndex(
            model_name="stationdirectthread",
            index=models.Index(
                fields=["station", "owner_archived_at"], name="chat_stadirec_station_0a1b2c_idx"
            ),
        ),
        migrations.CreateModel(
            name="StationDirectMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="Текст")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="station_direct_messages",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Отправитель",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="chat.stationdirectthread",
                        verbose_name="Чат",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сообщение (чат со станцией)",
                "verbose_name_plural": "Сообщения (чаты со станциями)",
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.AddIndex(
            model_name="stationdirectmessage",
            index=models.Index(fields=["thread", "created_at"], name="chat_stadirec_thread_2c3d4e_idx"),
        ),
    ]
