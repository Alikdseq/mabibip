import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0004_rename_reviews_rev_status_8d6cf6_idx_reviews_rev_status_4ac366_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewReply",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="Текст ответа")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "review",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owner_reply",
                        to="reviews.review",
                        verbose_name="Отзыв",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ответ на отзыв",
                "verbose_name_plural": "Ответы на отзывы",
            },
        ),
    ]
