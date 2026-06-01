from datetime import timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from simple_history.models import HistoricalRecords

from apps.bookings.models import Booking

# Сценарий ЛК: клиент может править текст/оценку отзыва после публикации ограниченное время.
REVIEW_CLIENT_EDIT_HOURS = 24


class ModerationStatus(models.TextChoices):
    OK = "ok", "OK"
    UNDER_REVIEW = "under_review", "На проверке"
    HIDDEN = "hidden", "Скрыт"


class ComplaintStatus(models.TextChoices):
    PENDING = "pending", "Ожидает разбора"
    RESOLVED = "resolved", "Решено"


class Review(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name="Бронирование",
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="station_reviews_written",
        verbose_name="Автор отзыва",
    )
    station = models.ForeignKey(
        "stations.ServiceStation",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="СТО / мастер",
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField("Текст", blank=True)
    photo = models.ImageField(
        "Фото",
        upload_to="reviews/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp"),
                message="Допустимы только изображения JPG, PNG или WEBP.",
            ),
        ],
        help_text="Необязательно, не более одного файла.",
    )
    photo_thumb = ImageSpecField(
        source="photo",
        processors=[ResizeToFit(width=720, height=540)],
        format="JPEG",
        options={"quality": 84},
    )
    moderation_status = models.CharField(
        "Статус модерации",
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.OK,
    )
    moderation_reason = models.CharField("Причина модерации", max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["author", "station"],
                name="reviews_author_station_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["station", "moderation_status", "-created_at"]),
        ]

    def __str__(self) -> str:
        if self.booking_id:
            return f"★{self.rating} — {self.booking}"
        return f"★{self.rating} — station {self.station_id}"

    def save(self, *args, **kwargs):
        if self.booking_id:
            if not self.author_id:
                self.author_id = self.booking.client_id
            if not self.station_id:
                self.station_id = self.booking.station_id
        super().save(*args, **kwargs)

    def is_editable_by_client(self, *, now=None) -> bool:
        now = now or timezone.now()
        return now < self.created_at + timedelta(hours=REVIEW_CLIENT_EDIT_HOURS)


class ReviewReply(models.Model):
    """Ответ владельца СТО под отзывом (публично на карточке)."""

    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name="owner_reply",
        verbose_name="Отзыв",
    )
    text = models.TextField("Текст ответа")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ответ на отзыв"
        verbose_name_plural = "Ответы на отзывы"

    def __str__(self) -> str:
        return f"Reply to review {self.review_id}"


class ReviewComplaint(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="complaints",
        verbose_name="Отзыв",
    )
    station = models.ForeignKey(
        "stations.ServiceStation",
        on_delete=models.CASCADE,
        related_name="review_complaints",
        verbose_name="СТО",
    )
    reason = models.CharField("Причина", max_length=300)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Жалоба на отзыв"
        verbose_name_plural = "Жалобы на отзывы"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Complaint({self.status}) review={self.review_id} station={self.station_id}"
