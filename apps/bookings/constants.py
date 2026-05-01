"""Статусы бронирования и сроки (шаг 0.4.2; дедлайн СТО — фаза 4)."""

from django.db import models


class BookingStatus(models.TextChoices):
    PENDING = "pending", "Ожидает подтверждения"
    CONFIRMED = "confirmed", "Подтверждено"
    IN_PROGRESS = "in_progress", "В работе"
    COMPLETED = "completed", "Завершено"
    CANCELED = "canceled", "Отменено"


# Час на подтверждение со стороны СТО (см. PLAN-MVP-ATOMIC §4.4)
STO_CONFIRM_DEADLINE_HOURS = 1
