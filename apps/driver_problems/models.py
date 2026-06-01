# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import models


class ProblemStatus(models.TextChoices):
    OPEN = "open", "Открыта"
    CLAIMED = "claimed", "В работе"
    CLOSED = "closed", "Закрыта"


class DriverProblemPost(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_problem_posts",
        verbose_name="Водитель",
    )
    title = models.CharField("Заголовок", max_length=120)
    description = models.TextField("Описание", max_length=2000)
    car_brand = models.CharField("Марка авто", max_length=80, blank=True, default="")
    city_label = models.CharField("Город", max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=ProblemStatus.choices,
        default=ProblemStatus.OPEN,
        db_index=True,
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_problems_claimed",
        verbose_name="Мастер",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Проблема водителя"
        verbose_name_plural = "Проблемы водителей"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.title
