"""Удаление всех пользователей, кроме одного (по телефону + email). Осторожно: CASCADE."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.users.phone_utils import PhoneValidationError, normalize_to_e164


class Command(BaseCommand):
    help = (
        "Удаляет все учётные записи User, кроме пользователя с указанными телефоном и email "
        "(оба условия должны совпасть). По умолчанию только показывает план; для выполнения передайте --execute."
    )

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True, help="Телефон (будет нормализован в E.164)")
        parser.add_argument("--email", required=True, help="Email сохраняемого пользователя")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Реально выполнить удаление (без флага только сводка)",
        )

    def handle(self, *args, **options):
        raw_phone = options["phone"].strip()
        email = options["email"].strip().lower()
        execute = options["execute"]

        try:
            phone = normalize_to_e164(raw_phone)
        except PhoneValidationError as e:
            raise CommandError(str(e)) from e

        User = get_user_model()
        keep = User.objects.filter(phone=phone, email__iexact=email).first()
        if keep is None:
            alt = User.objects.filter(phone=phone).first()
            if alt:
                raise CommandError(
                    f"Найден пользователь с телефоном {phone}, но email «{alt.email}» не совпадает с «{email}». "
                    "Исправьте данные или явно подтвердите учётку в БД."
                )
            raise CommandError(
                f"Пользователь с телефоном {phone} и email {email} не найден. Удаление отменено."
            )

        others = User.objects.exclude(pk=keep.pk)
        n = others.count()
        self.stdout.write(f"Сохраняем: pk={keep.pk} phone={keep.phone} email={keep.email}")
        self.stdout.write(f"К удалению записей User: {n}")

        if not execute:
            self.stdout.write(
                self.style.WARNING("Добавьте --execute для фактического удаления (CASCADE по связанным данным).")
            )
            return

        deleted = others.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено (сводка django ORM): {deleted}"))

