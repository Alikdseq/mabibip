# -*- coding: utf-8 -*-

from django.conf import settings
from django.db import models


class HelpRequestStatus(models.TextChoices):
    ACTIVE = "active", "Активно"
    RESOLVED = "resolved", "Закрыто"


class DriverHelpRequest(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_requests",
        verbose_name="Автор",
    )
    message = models.TextField("Сообщение", max_length=500)
    status = models.CharField(
        max_length=16,
        choices=HelpRequestStatus.choices,
        default=HelpRequestStatus.ACTIVE,
        db_index=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="help_requests_resolved",
        verbose_name="Закрыл",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запрос помощи"
        verbose_name_plural = "Запросы помощи"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Help #{self.pk} ({self.status})"
