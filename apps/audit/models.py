from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    F7.1.2: кастомные события, не покрытые model history
    (массовые действия, ручные блокировки, рассылки и т.п.).
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
        verbose_name="Кто",
    )
    event_type = models.CharField("Тип события", max_length=80, db_index=True)

    action = models.CharField(
        "Действие",
        max_length=40,
        blank=True,
        default="",
        help_text="Короткое действие для фильтрации: create/update/delete/approve/etc.",
    )

    object_type = models.CharField(
        "Тип объекта",
        max_length=80,
        blank=True,
        default="",
        help_text="Напр. users.User, stations.ServiceStation, bookings.Booking",
    )
    object_id = models.BigIntegerField("ID объекта", null=True, blank=True)

    object_label = models.CharField("Объект", max_length=200, blank=True, default="")
    payload = models.JSONField("Детали", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)

    request_path = models.CharField("URL", max_length=300, blank=True, default="")
    method = models.CharField("Метод", max_length=10, blank=True, default="")
    user_agent = models.CharField("User-Agent", max_length=300, blank=True, default="")
    status_code = models.SmallIntegerField("HTTP статус", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "AuditLog"
        verbose_name_plural = "AuditLog"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["object_type", "object_id", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} by actor_id={self.actor_id}"

