from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("stations", "0004_f4_billing_blocked_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="moderation_status",
            field=models.CharField(
                choices=[("ok", "OK"), ("under_review", "На проверке"), ("hidden", "Скрыт")],
                default="ok",
                max_length=20,
                verbose_name="Статус модерации",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="moderation_reason",
            field=models.CharField(blank=True, default="", max_length=300, verbose_name="Причина модерации"),
        ),
        migrations.CreateModel(
            name="ReviewComplaint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(max_length=300, verbose_name="Причина")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Ожидает разбора"), ("resolved", "Решено")],
                        default="pending",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="complaints",
                        to="reviews.review",
                        verbose_name="Отзыв",
                    ),
                ),
                (
                    "station",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review_complaints",
                        to="stations.servicestation",
                        verbose_name="СТО",
                    ),
                ),
            ],
            options={
                "verbose_name": "Жалоба на отзыв",
                "verbose_name_plural": "Жалобы на отзывы",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="reviewcomplaint",
            index=models.Index(fields=["status", "-created_at"], name="reviews_rev_status_8d6cf6_idx"),
        ),
    ]

