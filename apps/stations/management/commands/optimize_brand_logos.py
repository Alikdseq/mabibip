"""Генерация WebP рядом с PNG/JPEG логотипами марок (меньший вес на мобильных)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.stations.templatetags.station_catalog import _brand_logo_dir


class Command(BaseCommand):
    help = (
        "Создаёт рядом с каждым logo/*.png|jpg файл .webp для <picture> (см. brand_logo_webp_relpath). "
        "Требуется Pillow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quality",
            type=int,
            default=82,
            help="Качество WebP (1–100), по умолчанию 82",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписать существующие .webp",
        )

    def handle(self, *args, **options):
        try:
            from PIL import Image
        except ImportError:
            self.stderr.write(self.style.ERROR("Установите Pillow (requirements/base.txt)."))
            raise SystemExit(1)

        quality = max(1, min(100, int(options["quality"])))
        force = bool(options["force"])
        d = _brand_logo_dir()
        if not d.is_dir():
            self.stderr.write(self.style.ERROR(f"Каталог логотипов не найден: {d}"))
            raise SystemExit(1)

        exts = {".png", ".jpg", ".jpeg"}
        done = 0
        skipped = 0
        for p in sorted(d.iterdir()):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            out = p.with_suffix(".webp")
            if out.is_file() and not force:
                skipped += 1
                continue
            try:
                im = Image.open(p)
                im.load()
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA")
                im.save(out, "WEBP", quality=quality, method=6)
                done += 1
                self.stdout.write(self.style.SUCCESS(f"OK {p.name} -> {out.name}"))
            except OSError as e:
                self.stderr.write(self.style.WARNING(f"Пропуск {p.name}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Готово: создано {done}, пропущено (уже есть) {skipped}."))
