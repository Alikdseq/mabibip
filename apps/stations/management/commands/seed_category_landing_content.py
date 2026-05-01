"""Заполнить landing_lead и landing_faq у ServiceCategory из пресетов (фаза D2)."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.stations.models import ServiceCategory
from apps.stations.seed_data.category_landing_presets import CATEGORY_LANDING_PRESETS


class Command(BaseCommand):
    help = "Обновить SEO-поля категорий из apps.stations.seed_data.category_landing_presets (только существующие slug)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что было бы обновлено",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        updated = 0
        skipped = 0
        for slug, payload in CATEGORY_LANDING_PRESETS.items():
            try:
                cat = ServiceCategory.objects.get(slug=slug)
            except ServiceCategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"нет категории slug={slug!r} — пропуск"))
                skipped += 1
                continue
            lead = (payload.get("lead") or "").strip()
            faq = payload.get("faq") or []
            if dry:
                self.stdout.write(f"[dry-run] {slug}: lead={len(lead)} симв., faq={len(faq)}")
                updated += 1
                continue
            cat.landing_lead = lead
            cat.landing_faq = faq
            cat.save(update_fields=["landing_lead", "landing_faq"])
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"обновлено: {slug}"))
        self.stdout.write(self.style.NOTICE(f"готово: обновлено {updated}, пропусков (нет в БД) {skipped}"))
