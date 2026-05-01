from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class CallStatus(models.TextChoices):
    INITIATED = "initiated", "Инициирован"
    RINGING = "ringing", "Звонит"
    ACTIVE = "active", "Активен"
    COMPLETED = "completed", "Завершён"
    MISSED = "missed", "Пропущен"
    DECLINED = "declined", "Отклонён"
    FAILED = "failed", "Ошибка"


class CallContextKind(models.TextChoices):
    # Важно: эти значения — публичные (логирование/клиент), меняйте аккуратно.
    NONE = "none", "—"
    AD = "ad", "Объявление"
    AD_DIRECT = "ad_direct", "Чат по объявлению"
    STATION_DIRECT = "station_direct", "Прямой чат"
    BOOKING_CHAT = "booking_chat", "Чат по записи"


class Call(models.Model):
    """
    WebRTC-звонок в браузере. Телефонные номера не участвуют.

    Комната создаётся в LiveKit; сигнализация — через Channels.
    """

    room_name = models.CharField("Комната LiveKit", max_length=255, unique=True, db_index=True)
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outgoing_calls",
        verbose_name="Звонящий",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incoming_calls",
        verbose_name="Получатель",
    )

    context_kind = models.CharField(
        "Контекст",
        max_length=20,
        choices=CallContextKind.choices,
        default=CallContextKind.NONE,
        db_index=True,
    )
    context_id = models.PositiveIntegerField("ID контекста", null=True, blank=True, db_index=True)
    ad = models.ForeignKey(
        "classifieds.Ad",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
        verbose_name="Объявление",
    )

    status = models.CharField(
        "Статус",
        max_length=20,
        choices=CallStatus.choices,
        default=CallStatus.INITIATED,
        db_index=True,
    )
    started_at = models.DateTimeField("Начат", null=True, blank=True)
    ended_at = models.DateTimeField("Завершён", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "звонок"
        verbose_name_plural = "звонки"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["caller", "receiver", "status"], name="calls_pair_status_idx"),
            models.Index(fields=["receiver", "status", "created_at"], name="calls_recv_status_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.room_name} ({self.status})"

    @property
    def is_active_like(self) -> bool:
        return self.status in (CallStatus.INITIATED, CallStatus.RINGING, CallStatus.ACTIVE)

    def mark_active(self) -> None:
        if self.status != CallStatus.ACTIVE:
            self.status = CallStatus.ACTIVE
        if not self.started_at:
            self.started_at = timezone.now()

    def mark_ended(self, *, status: str) -> None:
        self.status = status
        if not self.ended_at:
            self.ended_at = timezone.now()

