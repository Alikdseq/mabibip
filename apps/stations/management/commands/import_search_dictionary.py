"""
Загрузка словаря «фраза → услуги» (формат как в списокзапросов.txt).

Пример строки:
  троит двигатель → Диагностика двигателя / Замена свечей / Замена катушек
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.stations.models import ServiceCategory, ServiceSearchPhrase
from apps.stations.search_text import normalize_search_text

# Подмена формулировок из словаря на уже принятые в каталоге названия (дополняйте по мере наполнения БД).
SERVICE_NAME_ALIASES: dict[str, str] = {
    "диагностика двигателя": "Компьютерная диагностика",
    "замена свечей": "Замена свечей зажигания / накаливания (дизель)",
    "замена катушек": "Замена свечей зажигания / накаливания (дизель)",
    "замена катушки зажигания": "Замена свечей зажигания / накаливания (дизель)",
    "замена бензонасоса": "Замена топливного насоса в баке (модуля)",
    "замена топливного насоса": "Замена топливного насоса в баке (модуля)",
    "сход развал": "Сход-развал 3D (регулировка углов установки колес)",
    "сход развал 3d": "Сход-развал 3D (регулировка углов установки колес)",
}


def _unique_category_slug(name: str) -> str:
    base = slugify(name)[:130] or "usluga"
    slug = base
    n = 0
    while ServiceCategory.objects.filter(slug=slug).exists():
        n += 1
        suffix = f"-{n}"
        slug = f"{base[: 130 - len(suffix)]}{suffix}"
    return slug


def _resolve_canonical_name(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s
    alias = SERVICE_NAME_ALIASES.get(s.casefold())
    return alias if alias else s


class Command(BaseCommand):
    help = "Импорт словаря поисковых фраз (файл со строками «фраза → услуга1 / услуга2»)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=str(Path(settings.BASE_DIR) / "списокзапросов.txt"),
            help="Путь к UTF-8 тексту со словарём",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только разбор и счётчики, без записи в БД",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Удалить все ServiceSearchPhrase перед импортом",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        dry_run: bool = options["dry_run"]
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f"Файл не найден: {path}"))
            return

        text = path.read_text(encoding="utf-8")
        phrase_lines = 0
        links = 0
        skipped = 0
        rows: list[tuple[str, str, int, str]] = []

        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if "→" not in raw:
                continue
            left, right = raw.split("→", 1)
            phrase = left.strip()
            if not phrase:
                continue
            if phrase[0] in ("\U0001f697", "\U0001f6de", "\U0001f6d1", "\u2699", "\U0001f4a1", "\U0001f6e0"):
                continue
            targets = [t.strip() for t in right.split("/") if t.strip()]
            if not targets:
                skipped += 1
                continue
            phrase_lines += 1
            pn = normalize_search_text(phrase)
            if not pn:
                skipped += 1
                continue
            for i, svc in enumerate(targets):
                canonical = _resolve_canonical_name(svc)
                if not canonical:
                    skipped += 1
                    continue
                weight = max(1, 10 - min(i, 5))
                rows.append((phrase, pn, canonical, weight))
                links += 1

        self.stdout.write(
            f"Разобрано фраз: {phrase_lines}, связей фраза→услуга: {links}, пропусков: {skipped}"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: записи в БД не создаются"))
            return

        with transaction.atomic():
            if options["truncate"]:
                n_del, _ = ServiceSearchPhrase.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Удалено поисковых фраз: {n_del}"))

            created_phrases = 0
            created_cats = 0
            for phrase, phrase_norm, canonical, weight in rows:
                cat = ServiceCategory.objects.filter(name__iexact=canonical).first()
                if cat is None:
                    cat = ServiceCategory.objects.create(
                        name=canonical,
                        slug=_unique_category_slug(canonical),
                    )
                    created_cats += 1
                obj, was_created = ServiceSearchPhrase.objects.get_or_create(
                    phrase_normalized=phrase_norm,
                    category=cat,
                    defaults={"phrase": phrase, "weight": weight},
                )
                if not was_created:
                    updates = []
                    if obj.phrase != phrase:
                        obj.phrase = phrase
                        updates.append("phrase")
                    if obj.weight != weight:
                        obj.weight = weight
                        updates.append("weight")
                    if updates:
                        obj.save(update_fields=updates + ["phrase_normalized"])
                else:
                    created_phrases += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Новых категорий: {created_cats}, новых записей фраз: {created_phrases}"
            )
        )
