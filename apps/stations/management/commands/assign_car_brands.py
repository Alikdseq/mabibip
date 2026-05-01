"""Назначить марки авто станциям/мастерам (для демо и быстрого заполнения каталога)."""

from __future__ import annotations

import hashlib

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.stations.models import CarBrand, ServiceStation


class Command(BaseCommand):
    help = (
        "Назначает каждой ServiceStation набор марок CarBrand так, чтобы наборы "
        "были разными между станциями (детерминированно от pk)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-station",
            type=int,
            default=3,
            help="Сколько марок назначить каждой станции (по умолчанию 3).",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Перед назначением очистить текущие car_brands у станции.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет сделано, без записи в БД.",
        )

    def handle(self, *args, **options):
        per_station: int = options["per_station"]
        replace: bool = options["replace"]
        dry_run: bool = options["dry_run"]

        if per_station < 1:
            raise SystemExit("--per-station должен быть >= 1")

        brands = list(CarBrand.objects.order_by("sort_order", "name", "pk"))
        if not brands:
            self.stderr.write(self.style.ERROR("В БД нет CarBrand. Сначала примените миграции/сид справочника."))
            return

        n = len(brands)
        stations = list(ServiceStation.objects.order_by("pk"))
        if not stations:
            self.stdout.write(self.style.WARNING("ServiceStation не найдены — нечего заполнять."))
            return

        planned: list[tuple[ServiceStation, list[CarBrand]]] = []
        for idx, st in enumerate(stations):
            # Детерминированный "якорь" (не зависит от PYTHONHASHSEED / версии Python).
            h = int(
                hashlib.sha256(f"{st.pk}:{st.slug}".encode("utf-8")).hexdigest()[:12],
                16,
            )
            # Смещаем старт по кругу, чтобы соседние pk не получали одинаковые окна.
            start = (idx * max(1, per_station) + (h % n)) % n
            picked: list[CarBrand] = []
            for k in range(per_station):
                picked.append(brands[(start + k) % n])
            # Уникальность внутри станции (если per_station > n — это невозможно без повторов)
            uniq: list[CarBrand] = []
            seen: set[int] = set()
            for b in picked:
                if b.pk in seen:
                    continue
                seen.add(b.pk)
                uniq.append(b)
            planned.append((st, uniq))

        if dry_run:
            for st, bs in planned[:20]:
                self.stdout.write(f"[dry-run] {st.slug}: " + ", ".join(b.slug for b in bs))
            if len(planned) > 20:
                self.stdout.write(f"... ещё станций: {len(planned) - 20}")
            return

        updated = 0
        with transaction.atomic():
            for st, bs in planned:
                if replace:
                    st.car_brands.clear()
                st.car_brands.add(*[b.pk for b in bs])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: обновлено станций: {updated}; марок в справочнике: {n}; per_station={per_station}; replace={replace}."
            )
        )
