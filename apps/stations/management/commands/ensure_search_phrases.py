"""Однократная подгрузка словаря фраз, если таблица пуста (Docker / новый стенд)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.stations.models import ServiceSearchPhrase


class Command(BaseCommand):
    help = "Если нет записей ServiceSearchPhrase — импорт из списокзапросов.txt в корне проекта."

    def handle(self, *args, **options):
        if ServiceSearchPhrase.objects.exists():
            return
        path = Path(settings.BASE_DIR) / "списокзапросов.txt"
        if not path.is_file():
            self.stderr.write(self.style.WARNING(f"Файл словаря не найден: {path}"))
            return
        self.stdout.write(self.style.NOTICE("Словарь подсказок пуст — импорт списокзапросов.txt …"))
        call_command("import_search_dictionary", file=str(path))
