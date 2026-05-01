"""Ручной запуск генерации слотов (догоняние без ожидания Celery Beat, фаза F3.1.3)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.bookings.slot_generation import run_generate_weekly_slots


class Command(BaseCommand):
    help = "Создаёт недостающие TimeSlot по WorkingHours на горизонт SLOT_GENERATION_DAYS_AHEAD (идемпотентно)."

    def handle(self, *args, **options):
        n = run_generate_weekly_slots()
        self.stdout.write(self.style.SUCCESS(f"Добавлено новых слотов (строк): {n}"))
