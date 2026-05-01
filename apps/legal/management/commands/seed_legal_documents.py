"""Загрузка Markdown из docs/legal/ в LegalDocumentVersion (фаза F0, шаг F0.1.1)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.legal.models import DocumentKey, LegalDocumentVersion

# Имя файла в репозитории → ключ enum (единый источник для деплоя).
FILE_MAP: dict[str, str] = {
    "privacy.md": DocumentKey.PRIVACY,
    "user_agreement.md": DocumentKey.USER_AGREEMENT,
    "pd_consent.md": DocumentKey.PD_CONSENT,
    "sto_offer.md": DocumentKey.STO_OFFER,
    "infosec_policy.md": DocumentKey.INFOSEC_POLICY,
    "paid_services.md": DocumentKey.PAID_SERVICES,
}


class Command(BaseCommand):
    help = "Создаёт или обновляет версии юридических документов из каталога docs/legal/*.md"

    def add_arguments(self, parser):
        parser.add_argument(
            "--version-label",
            default="1.0",
            help=(
                "Метка версии (уникальна в паре с типом документа), "
                'например "1.0" или "2026-04-15".'
            ),
        )
        parser.add_argument(
            "--effective-now",
            action="store_true",
            help=(
                "Вступление в силу — текущий момент "
                "(иначе можно расширить команду под свою дату)."
            ),
        )

    def handle(self, *args, **options):
        version_label: str = options["version_label"]
        root = Path(settings.BASE_DIR) / "docs" / "legal"
        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f"Каталог не найден: {root}"))
            return

        effective_at = timezone.now() if options["effective_now"] else timezone.now()
        # Важно: для публикации новой редакции в проде используйте новый --version-label,
        # чтобы сохранялся архив версий и история согласий пользователя.

        for filename, key in FILE_MAP.items():
            path = root / filename
            if not path.is_file():
                self.stderr.write(self.style.WARNING(f"Пропуск (нет файла): {path}"))
                continue
            text = path.read_text(encoding="utf-8")
            title = dict(DocumentKey.choices).get(key, filename)
            obj, created = LegalDocumentVersion.objects.update_or_create(
                key=key,
                version_label=version_label,
                defaults={
                    "title": title,
                    "effective_at": effective_at,
                    "content_markdown": text,
                },
            )
            action = "Создан" if created else "Обновлён"
            self.stdout.write(self.style.SUCCESS(f"{action}: {obj}"))
