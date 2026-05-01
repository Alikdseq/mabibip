"""Модели приложения «Ядро»."""

from __future__ import annotations

from django.db import models


class CityExpansionSignal(models.Model):
    """
    Сигнал для ERP: бизнес-роли регистрируются из нового города → нужно «расширяться».

    Не блокирует регистрацию/город в формах; это только индикатор для админа.
    """

    city_label = models.CharField("Город", max_length=120, unique=True, db_index=True)
    seen_count = models.PositiveIntegerField("Сколько регистраций бизнеса", default=0)
    first_seen_at = models.DateTimeField("Первое появление", auto_now_add=True, db_index=True)
    last_seen_at = models.DateTimeField("Последнее появление", auto_now=True, db_index=True)
    acknowledged = models.BooleanField("Админ подтвердил («Отлично»)", default=False, db_index=True)

    class Meta:
        verbose_name = "сигнал расширения города"
        verbose_name_plural = "сигналы расширения городов"
        ordering = ["acknowledged", "-last_seen_at", "city_label"]

    def __str__(self) -> str:
        return f"{self.city_label} (count={self.seen_count}, ok={self.acknowledged})"
