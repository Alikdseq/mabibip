"""Модели версий юридических документов и фиксации согласий пользователя (фаза F0)."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


class DocumentKey(models.TextChoices):
    """Ключи документов из части 1 ТЗ — один активный набор версий на ключ."""

    PRIVACY = "privacy", "Политика конфиденциальности"
    USER_AGREEMENT = "user_agreement", "Пользовательское соглашение"
    PD_CONSENT = "pd_consent", "Согласие на обработку персональных данных"
    STO_OFFER = "sto_offer", "Лицензионный договор-оферта (СТО)"
    INFOSEC_POLICY = "infosec_policy", "Политика информационной безопасности"
    PAID_SERVICES = "paid_services", "Оферта на оказание платных услуг"


def _checksum(text: str) -> str:
    # Контроль целостности текста для аудита: при смене файла меняется checksum.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LegalDocumentVersion(models.Model):
    key = models.CharField(
        "Тип документа",
        max_length=32,
        choices=DocumentKey.choices,
        db_index=True,
    )
    version_label = models.CharField(
        "Версия (метка)",
        max_length=64,
        help_text='Например "1.0" или дата релиза.',
    )
    title = models.CharField("Заголовок для отображения", max_length=255)
    effective_at = models.DateTimeField(
        "Дата вступления в силу",
        db_index=True,
        help_text="Документ считается действующим с этого момента (UTC хранится, показ в МСК на фронте при необходимости).",
    )
    content_markdown = models.TextField(
        "Текст в Markdown",
        help_text="Исходник для публичной страницы; рендер с санитизацией HTML.",
    )
    content_checksum = models.CharField(
        "SHA-256 текста",
        max_length=64,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Версия юридического документа"
        verbose_name_plural = "Версии юридических документов"
        constraints = [
            models.UniqueConstraint(
                fields=("key", "version_label"),
                name="legal_unique_key_version_label",
            ),
        ]
        indexes = [
            models.Index(fields=("key", "-effective_at")),
        ]

    def __str__(self) -> str:
        return f"{self.get_key_display()} v{self.version_label}"

    def save(self, *args, **kwargs) -> None:
        self.content_checksum = _checksum(self.content_markdown)
        super().save(*args, **kwargs)


class UserConsent(models.Model):
    """Фиксация принятия конкретной версии документа (доказательная база по 152-ФЗ)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_consents",
        verbose_name="Пользователь",
    )
    document_version = models.ForeignKey(
        LegalDocumentVersion,
        on_delete=models.PROTECT,
        related_name="user_consents",
        verbose_name="Версия документа",
    )
    accepted_at = models.DateTimeField("Принято", auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        "IP-адрес",
        null=True,
        blank=True,
        help_text="Опционально: фиксируйте только при согласии с юристом (минимизация ПДн).",
    )
    user_agent = models.CharField(
        "User-Agent (укороченный)",
        max_length=256,
        blank=True,
    )

    class Meta:
        verbose_name = "Согласие пользователя"
        verbose_name_plural = "Согласия пользователей"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "document_version"),
                name="legal_unique_user_document_version",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "-accepted_at")),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.document_version_id}"


def get_current_version(key: str, *, at: datetime | None = None) -> LegalDocumentVersion | None:
    """
    Актуальная версия документа: последняя по времени вступления, уже вступившая в силу.
    Один источник правды для middleware и форм регистрации.
    """
    moment = at if at is not None else timezone.now()
    return (
        LegalDocumentVersion.objects.filter(key=key, effective_at__lte=moment)
        .order_by("-effective_at", "-id")
        .first()
    )


REGISTRATION_REQUIRED_KEYS: tuple[str, ...] = (
    DocumentKey.PRIVACY,
    DocumentKey.USER_AGREEMENT,
    DocumentKey.PD_CONSENT,
)
