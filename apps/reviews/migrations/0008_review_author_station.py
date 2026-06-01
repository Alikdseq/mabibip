# Generated manually for open station reviews

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_review_author_station(apps, schema_editor):
    Review = apps.get_model("reviews", "Review")
    for review in Review.objects.select_related("booking").filter(booking__isnull=False):
        review.author_id = review.booking.client_id
        review.station_id = review.booking.station_id
        review.save(update_fields=["author_id", "station_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("reviews", "0007_alter_historicalreview_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="author",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="station_reviews_written",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Автор отзыва",
            ),
        ),
        migrations.AddField(
            model_name="review",
            name="station",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews",
                to="stations.servicestation",
                verbose_name="СТО / мастер",
            ),
        ),
        migrations.RunPython(backfill_review_author_station, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="review",
            name="author",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="station_reviews_written",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Автор отзыва",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="station",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews",
                to="stations.servicestation",
                verbose_name="СТО / мастер",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="booking",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="review",
                to="bookings.booking",
                verbose_name="Бронирование",
            ),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.UniqueConstraint(
                fields=("author", "station"),
                name="reviews_author_station_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["station", "moderation_status", "-created_at"],
                name="reviews_rev_station_mod_idx",
            ),
        ),
    ]
