# Generated manually.

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("classifieds", "0008_ad_view_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="SellerReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                        verbose_name="Оценка",
                    ),
                ),
                ("text", models.TextField(blank=True, default="", verbose_name="Текст")),
                (
                    "moderation_status",
                    models.CharField(
                        choices=[
                            ("ok", "OK"),
                            ("under_review", "На проверке"),
                            ("hidden", "Скрыт"),
                        ],
                        db_index=True,
                        default="ok",
                        max_length=20,
                        verbose_name="Статус модерации",
                    ),
                ),
                (
                    "moderation_reason",
                    models.CharField(blank=True, default="", max_length=300, verbose_name="Причина модерации"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classifieds_seller_reviews_written",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Автор отзыва",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classifieds_seller_reviews_received",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Продавец",
                    ),
                ),
            ],
            options={
                "verbose_name": "Отзыв о продавце (объявления)",
                "verbose_name_plural": "Отзывы о продавцах (объявления)",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="sellerreview",
            constraint=models.UniqueConstraint(
                fields=("author", "seller"),
                name="classifieds_sellerreview_author_seller_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="sellerreview",
            index=models.Index(
                fields=["seller", "moderation_status", "-created_at"],
                name="clsfd_sellrev_seller_stat_cr",
            ),
        ),
    ]
