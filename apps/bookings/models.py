from datetime import time as time_cls

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.stations.models import ServiceStation, WorkBay

from .constants import BookingStatus


class WorkingHours(models.Model):
    """
    Шаблон расписания поста по дням неделя (фаза F3): окно работы, шаг слота, перерывы.
    """

    WEEKDAY_CHOICES = (
        (0, "Понедельник"),
        (1, "Вторник"),
        (2, "Среда"),
        (3, "Четверг"),
        (4, "Пятница"),
        (5, "Суббота"),
        (6, "Воскресенье"),
    )

    bay = models.ForeignKey(
        WorkBay,
        on_delete=models.CASCADE,
        related_name="working_hours",
        verbose_name="Пост",
    )
    weekday = models.PositiveSmallIntegerField(
        "День недели",
        choices=WEEKDAY_CHOICES,
        help_text="0 — понедельник … 6 — воскресенье (как date.weekday()).",
    )
    opens_at = models.TimeField("Открытие")
    closes_at = models.TimeField("Закрытие")
    slot_duration_minutes = models.PositiveSmallIntegerField(
        "Длительность слота, мин",
        default=30,
    )
    breaks = models.JSONField(
        "Перерывы",
        default=list,
        blank=True,
        help_text='JSON-массив интервалов, напр. [{"start": "12:00", "end": "13:00"}].',
    )

    class Meta:
        verbose_name = "Расписание поста"
        verbose_name_plural = "Расписания постов"
        constraints = [
            models.UniqueConstraint(fields=["bay", "weekday"], name="bookings_workinghours_bay_weekday_uniq"),
        ]
        ordering = ["bay_id", "weekday"]

    def __str__(self) -> str:
        return f"{self.bay} — {self.get_weekday_display()} {self.opens_at}–{self.closes_at}"

    def clean(self):
        super().clean()
        if self.opens_at and self.closes_at and self.opens_at >= self.closes_at:
            raise ValidationError("Время открытия должно быть раньше закрытия.")
        if self.slot_duration_minutes and self.slot_duration_minutes < 5:
            raise ValidationError("Минимальный шаг слота — 5 минут.")
        raw = self.breaks or []
        if not isinstance(raw, list):
            raise ValidationError("Перерывы должны быть списком объектов.")
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValidationError(f"Перерыв #{i + 1}: ожидается объект.")
            try:
                hs, ms = map(int, str(item["start"]).split(":"))
                he, me = map(int, str(item["end"]).split(":"))
            except (KeyError, ValueError) as e:
                raise ValidationError(f"Перерыв #{i + 1}: нужны поля start/end в формате ЧЧ:ММ.") from e

            t_s, t_e = time_cls(hs, ms), time_cls(he, me)
            if t_s >= t_e:
                raise ValidationError(f"Перерыв #{i + 1}: start должен быть раньше end.")


class TimeSlot(models.Model):
    bay = models.ForeignKey(
        WorkBay,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name="Пост",
    )
    date = models.DateField("Дата")
    start_time = models.TimeField("Начало")
    end_time = models.TimeField("Окончание")
    is_available = models.BooleanField("Доступно для записи", default=True)
    manual_block_note = models.CharField(
        "Причина закрытия (для себя)",
        max_length=200,
        blank=True,
        default="",
        help_text="Комментарий при ручном закрытии слота в календаре (клиентам не показывается).",
    )
    reserved_until = models.DateTimeField(
        "Зарезервировано до",
        null=True,
        blank=True,
        help_text="Удержание слота без подтверждённой брони.",
    )

    class Meta:
        verbose_name = "Окно записи"
        verbose_name_plural = "Окна записи"
        ordering = ["date", "start_time", "pk"]
        indexes = [
            models.Index(fields=["bay", "date", "start_time"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bay", "date", "start_time"],
                name="bookings_timeslot_bay_date_start_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.start_time}—{self.end_time} ({self.bay})"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Время начала должно быть раньше времени окончания.")
        if self._state.adding and self.date:
            today = timezone.localdate()
            if self.date < today:
                raise ValidationError("Нельзя создавать слот в прошлом.")


class Booking(models.Model):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Клиент",
    )
    station = models.ForeignKey(
        ServiceStation,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="СТО",
    )
    slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Слот",
    )
    car_info = models.CharField("Авто (госномер / марка)", max_length=100)
    contact_phone = models.CharField("Телефон для связи", max_length=20)
    description = models.TextField("Описание проблемы")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    sto_confirm_deadline = models.DateTimeField(
        "Подтвердить до",
        null=True,
        blank=True,
        help_text="Истечение ожидания подтверждения СТО (создание + 1 ч).",
    )
    reminder_2h_sent_at = models.DateTimeField(
        "Напоминание за 2 ч отправлено",
        null=True,
        blank=True,
    )
    owner_cancel_reason = models.CharField(
        "Причина отмены (СТО)",
        max_length=500,
        blank=True,
        default="",
        help_text="Кратко для клиента при отмене записи из кабинета СТО.",
    )
    reschedule_proposed_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Предложенный слот (перенос)",
    )
    reschedule_owner_message = models.CharField(
        "Сообщение клиенту при переносе",
        max_length=500,
        blank=True,
        default="",
        help_text="Текст от мастера/СТО: почему предлагается другое время.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client"]),
            models.Index(fields=["station"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(
                    status__in=[
                        BookingStatus.PENDING,
                        BookingStatus.CONFIRMED,
                        BookingStatus.IN_PROGRESS,
                    ]
                ),
                name="booking_slot_unique_active",
            ),
        ]

    def __str__(self) -> str:
        return f"Бронь #{self.pk} {self.station.name}"

    def can_transition_to(self, new_status: str, actor) -> bool:
        from apps.bookings.services import can_booking_transition_to

        return can_booking_transition_to(self, new_status, actor)
