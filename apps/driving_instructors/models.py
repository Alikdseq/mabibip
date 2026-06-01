# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class TransmissionType(models.TextChoices):
    MANUAL = "manual", "Механика"
    AUTOMATIC = "automatic", "Автомат"
    BOTH = "both", "Обе"


class DrivingInstructorProfile(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="instructor_profile",
        verbose_name="Инструктор",
    )
    name = models.CharField("Имя / название", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)
    city_label = models.CharField("Город", max_length=120, blank=True, default="")
    address = models.CharField("Адрес / район", max_length=500, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    contact_phone = models.CharField("Телефон", max_length=32, blank=True, default="")
    transmission = models.CharField(
        max_length=16,
        choices=TransmissionType.choices,
        default=TransmissionType.BOTH,
    )
    experience_years = models.PositiveSmallIntegerField("Стаж (лет)", default=0)
    price_per_hour = models.DecimalField(
        "Цена за час, ₽",
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
    )
    price_exam_package = models.DecimalField(
        "Пакет к экзамену, ₽",
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
    )
    services_text = models.CharField(
        "Услуги",
        max_length=500,
        blank=True,
        default="",
        help_text="Через запятую: город, площадка, экзамен…",
    )
    is_published = models.BooleanField("В каталоге", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Автоинструктор"
        verbose_name_plural = "Автоинструкторы"
        ordering = ["name", "pk"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "instructor"
            slug = base
            n = 0
            qs = DrivingInstructorProfile.objects.exclude(pk=self.pk) if self.pk else DrivingInstructorProfile.objects.all()
            while qs.filter(slug=slug).exists():
                n += 1
                slug = f"{base[:200-len(str(n))-1]}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)
