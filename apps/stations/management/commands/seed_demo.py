"""Демо-данные для каталога (фаза 3.5)."""

from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import TimeSlot
from apps.stations.constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.users.models import User


class Command(BaseCommand):
    help = "Создаёт демо-станции, посты и слоты (без тяжёлых файлов фото)."

    def handle(self, *args, **options):
        today = timezone.now().date()
        owner, _ = User.objects.get_or_create(
            phone="+79990001234",
            defaults={
                "email": "owner-demo@promaster.local",
                "is_sto_owner": True,
                "is_active": True,
                "is_phone_verified": True,
            },
        )
        if not owner.has_usable_password():
            owner.set_password("demo-owner-pass")
            owner.save(update_fields=["password"])

        names = [
            ("АвтоСервис Север", "ул. Северная, 1", SUBSCRIPTION_PLAN_FREE),
            ("Мастерская Юг", "пр. Южный, 10", SUBSCRIPTION_PLAN_BASIC),
            ("Пит-Стоп Центр", "ул. Центральная, 5", SUBSCRIPTION_PLAN_BASIC),
        ]
        for i, (name, addr, plan) in enumerate(names):
            paid = today + timedelta(days=30) if plan == SUBSCRIPTION_PLAN_BASIC else None
            st, created = ServiceStation.objects.get_or_create(
                slug=f"demo-{i}",
                defaults={
                    "owner": owner,
                    "name": name,
                    "address": addr,
                    "description": f"Демо-описание для «{name}».",
                    "subscription_plan": plan,
                    "subscription_paid_until": paid,
                    "is_active": True,
                },
            )
            if not created:
                continue
            bay = WorkBay.objects.create(station=st, name="Пост 1")
            TimeSlot.objects.create(
                bay=bay,
                date=today,
                start_time=time(9, 0),
                end_time=time(11, 0),
                is_available=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Создано СТО: {st.name}"))

        self.stdout.write(
            self.style.SUCCESS("Готово. Владелец: +79990001234 / demo-owner-pass (email: owner-demo@promaster.local)")
        )
