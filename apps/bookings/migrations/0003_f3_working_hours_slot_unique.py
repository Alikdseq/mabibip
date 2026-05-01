import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_phase4_slots_booking"),
        ("stations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkingHours",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "weekday",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Понедельник"),
                            (1, "Вторник"),
                            (2, "Среда"),
                            (3, "Четверг"),
                            (4, "Пятница"),
                            (5, "Суббота"),
                            (6, "Воскресенье"),
                        ],
                        help_text="0 — понедельник … 6 — воскресенье (как date.weekday()).",
                        verbose_name="День недели",
                    ),
                ),
                ("opens_at", models.TimeField(verbose_name="Открытие")),
                ("closes_at", models.TimeField(verbose_name="Закрытие")),
                (
                    "slot_duration_minutes",
                    models.PositiveSmallIntegerField(default=30, verbose_name="Длительность слота, мин"),
                ),
                (
                    "breaks",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='JSON-массив интервалов, напр. [{"start": "12:00", "end": "13:00"}].',
                        verbose_name="Перерывы",
                    ),
                ),
                (
                    "bay",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="working_hours",
                        to="stations.workbay",
                        verbose_name="Пост",
                    ),
                ),
            ],
            options={
                "verbose_name": "Расписание поста",
                "verbose_name_plural": "Расписания постов",
                "ordering": ["bay_id", "weekday"],
            },
        ),
        migrations.AddConstraint(
            model_name="workinghours",
            constraint=models.UniqueConstraint(fields=("bay", "weekday"), name="bookings_workinghours_bay_weekday_uniq"),
        ),
        migrations.AddConstraint(
            model_name="timeslot",
            constraint=models.UniqueConstraint(
                fields=("bay", "date", "start_time"),
                name="bookings_timeslot_bay_date_start_uniq",
            ),
        ),
    ]
