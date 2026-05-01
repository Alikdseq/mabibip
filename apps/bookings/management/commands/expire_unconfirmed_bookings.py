"""Автоотмена просроченных заявок в статусе pending (фаза 4.4)."""

from django.core.management.base import BaseCommand

from apps.bookings.services import expire_unconfirmed_bookings_now


class Command(BaseCommand):
    help = "Переводит pending-брони с истёкшим sto_confirm_deadline в canceled."

    def handle(self, *args, **options):
        n = expire_unconfirmed_bookings_now()
        self.stdout.write(self.style.SUCCESS(f"Отменено заявок: {n}"))
