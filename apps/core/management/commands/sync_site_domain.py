"""Синхронизация django.contrib.sites с SITE_BASE_URL (абсолютные URL в sitemap и письмах)."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Обновить Site.domain по SITE_BASE_URL (без слэша в конце переменной)."

    def handle(self, *args, **options):
        raw = (getattr(settings, "SITE_BASE_URL", None) or "").strip()
        if not raw:
            self.stdout.write(self.style.WARNING("SITE_BASE_URL пуст — пропуск."))
            return
        parsed = urlparse(raw)
        if not parsed.netloc:
            self.stdout.write(self.style.ERROR(f"Некорректный SITE_BASE_URL: {raw!r}"))
            return
        site_id = int(getattr(settings, "SITE_ID", 1))
        updated = Site.objects.filter(pk=site_id).update(domain=parsed.netloc, name=parsed.netloc)
        if not updated:
            self.stdout.write(
                self.style.WARNING(
                    f"Запись Site id={site_id} не найдена — выполните migrate (django.contrib.sites)."
                )
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Site id={site_id}: domain={parsed.netloc!r}"))
