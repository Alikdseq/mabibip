from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0002_f6_complaints_moderation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoricalReview",
            fields=[
                ("history_id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id", models.BigIntegerField(db_index=True, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField(verbose_name="Оценка")),
                ("text", models.TextField(blank=True, verbose_name="Текст")),
                ("moderation_status", models.CharField(choices=[("ok", "OK"), ("under_review", "На проверке"), ("hidden", "Скрыт")], default="ok", max_length=20, verbose_name="Статус модерации")),
                ("moderation_reason", models.CharField(blank=True, default="", max_length=300, verbose_name="Причина модерации")),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("history_date", models.DateTimeField()),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                ("history_type", models.CharField(max_length=1)),
                (
                    "booking",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to="bookings.booking", verbose_name="Бронирование"),
                ),
                (
                    "history_user",
                    models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "historical Отзыв",
                "verbose_name_plural": "historical Отзывы",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
        ),
    ]

