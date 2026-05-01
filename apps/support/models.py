from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class SupportTicketStatus(models.TextChoices):
    OPEN = "open", "Открыт"
    IN_PROGRESS = "in_progress", "В работе"
    RESOLVED = "resolved", "Решён"
    CLOSED = "closed", "Закрыт"


class SupportTicket(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        verbose_name="Пользователь",
    )
    subject = models.CharField("Тема", max_length=200, blank=True, default="")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=SupportTicketStatus.choices,
        default=SupportTicketStatus.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    user_last_read_at = models.DateTimeField(
        "Пользователь прочитал до",
        null=True,
        blank=True,
        db_index=True,
        help_text="Время последнего просмотра переписки пользователем в ЛК.",
    )
    staff_last_read_at = models.DateTimeField(
        "Персонал ERP прочитал до",
        null=True,
        blank=True,
        db_index=True,
        help_text="Время последнего просмотра тикета в ERP.",
    )

    class Meta:
        verbose_name = "Обращение в поддержку"
        verbose_name_plural = "Обращения в поддержку"
        ordering = ["-updated_at", "-pk"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.user_id} ({self.get_status_display()})"


class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Обращение",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_messages",
        verbose_name="Автор",
        help_text="Пусто — системное сообщение.",
    )
    body = models.TextField("Текст")
    is_staff_reply = models.BooleanField("Ответ поддержки", default=False, db_index=True)
    is_system_auto = models.BooleanField("Авто-сообщение", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Сообщение поддержки"
        verbose_name_plural = "Сообщения поддержки"
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"msg#{self.pk} ticket={self.ticket_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        SupportTicket.objects.filter(pk=self.ticket_id).update(updated_at=timezone.now())
