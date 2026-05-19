"""
Пакетный импорт мастеров/автосервисов/магазинов из apps.stations.seed_data.bulk_masters_may2026.

Пример на сервере:
  python manage.py import_masters_batch --dry-run
  python manage.py import_masters_batch
  python manage.py import_masters_batch --save-credentials /tmp/masters_passwords.txt
"""

from __future__ import annotations

import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classifieds.models import AutoShopProfile
from apps.core.city_expansion import record_business_city
from apps.stations.constants import (
    EXECUTOR_KIND_PRIVATE,
    EXECUTOR_KIND_STO,
    SUBSCRIPTION_PLAN_FREE,
)
from apps.stations.models import CarBrand, District, ServiceCategory, ServiceStation, StationServiceOffer
from apps.stations.seed_data.bulk_masters_may2026 import MASTER_ENTRIES, MasterSeed
from apps.users.phone_utils import PhoneValidationError, normalize_to_e164

User = get_user_model()

# Ключ специализации → ключевые слова для поиска ServiceCategory.name
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "electric": ("электрик", "электро", "диагностик", "проводк"),
    "paint": ("покраск", "маляр", "кузовн"),
    "detailing": ("детейлинг", "полиров", "химчист"),
    "bodywork": ("кузов", "рихтов", "жестян", "вмятин"),
    "plastic": ("пластик", "бампер", "пайк", "пластиков"),
    "engine": ("двигател", "мотор"),
    "diagnostic_full": ("диагностик", "компьютерн", "ходов", "подвеск", "двигател", "кпп", "коробк"),
    "diagnostic_grm": ("диагностик", "грм", "ремень", "ходов", "подвеск", "то "),
    "cooling": ("охлажден", "радиатор", "антифриз", "помп"),
    "gbo": ("гбо", "газобаллон", "газов"),
    "land_rover": ("ходов", "диагностик", "двигател"),
    "dismantle": ("разбор", "запчаст"),
    "paint_match": ("покраск", "подбор", "краск"),
    "exhaust": ("глушит", "выхлоп"),
    "radiator": ("радиатор", "диск", "тормоз"),
    "tires_shop": ("шин", "колес"),
    "parts_shop": ("запчаст",),
    "general": ("диагностик", "ремонт", "то "),
}

DESCRIPTIONS: dict[str, str] = {
    "electric": (
        "Электрика и компьютерная диагностика автомобиля. Ремонт проводки, стартера, "
        "генератора, поиск неисправностей. Работаем с понятной сметой до начала ремонта."
    ),
    "paint": (
        "Малярные работы и покраска: подготовка поверхности, нанесение ЛКМ, локальная "
        "и полная окраска. Поможем восстановить внешний вид автомобиля."
    ),
    "detailing": (
        "Детейлинг: мойка, полировка, защитные покрытия, химчистка салона. "
        "Аккуратная работа и внимание к деталям."
    ),
    "bodywork": (
        "Жестяные работы: рихтовка, восстановление кузовных элементов, подготовка под покраску."
    ),
    "plastic": (
        "Ремонт пластиковых деталей: пайка, склейка, восстановление бамперов и обвеса."
    ),
    "engine": (
        "Ремонт двигателя и агрегатов: диагностика, устранение неисправностей, "
        "обслуживание подкапотного пространства."
    ),
    "diagnostic_full": (
        "Диагностика, ремонт ходовой части, двигателя и КПП. Иномарки и отечественные автомобили."
    ),
    "diagnostic_grm": (
        "Диагностика, ремонт ходовой, замена ГРМ, обслуживание подкапотного пространства."
    ),
    "cooling": (
        "Аппаратная промывка и обслуживание системы охлаждения. Радиаторы, помпы, термостаты."
    ),
    "gbo": (
        "Установка и обслуживание ГБО. Подбор комплекта, монтаж, настройка и диагностика системы."
    ),
    "land_rover": (
        "Ремонт и обслуживание Range Rover / Land Rover: диагностика, ходовая, электрика, двигатель."
    ),
    "dismantle": (
        "Разборка автомобилей и подбор запчастей. Консультация по наличию и совместимости."
    ),
    "paint_match": (
        "Профессиональный подбор автомобильной краски по образцу и коду."
    ),
    "exhaust": (
        "Ремонт и замена элементов выхлопной системы, глушителей и соединений."
    ),
    "radiator": (
        "Ремонт радиаторов охлаждения и кондиционера, правка дисков, работы с топливными баками "
        "(в т.ч. грузовые автомобили)."
    ),
    "tires_shop": (
        "Продажа б/у шин и дисков. Подбор по размеру, консультация и проверка состояния."
    ),
    "parts_shop": (
        "Магазин автозапчастей: подбор деталей, консультация, широкий ассортимент расходников."
    ),
    "general": (
        "Ремонт и обслуживание автомобилей. Диагностика, консультация, запись через МаБибип."
    ),
}

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _translit_word(word: str) -> str:
    out = []
    for ch in word.casefold():
        if ch in _CYRILLIC_TO_LATIN:
            out.append(_CYRILLIC_TO_LATIN[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
    return "".join(out) or "master"


def _make_password(seed: MasterSeed, phone_e164: str) -> str:
    if seed.password:
        return seed.password
    first = re.split(r"[\s—\-–]+", (seed.name or "").strip())[0]
    base = _translit_word(first)[:12] or "master"
    digits = re.sub(r"\D", "", phone_e164)[-4:]
    pwd = f"{base}{digits}"
    if len(pwd) < 8:
        pwd = f"{base}2026"
    return pwd[:32]


def _find_categories(specialty_key: str) -> list[ServiceCategory]:
    keywords = CATEGORY_KEYWORDS.get(specialty_key) or CATEGORY_KEYWORDS["general"]
    found: list[ServiceCategory] = []
    seen: set[int] = set()
    for kw in keywords:
        for cat in ServiceCategory.objects.filter(name__icontains=kw).order_by("name")[:4]:
            if cat.pk in seen:
                continue
            seen.add(cat.pk)
            found.append(cat)
            if len(found) >= 5:
                return found
    if not found:
        for cat in ServiceCategory.objects.filter(name__icontains="диагност").order_by("name")[:2]:
            if cat.pk not in seen:
                found.append(cat)
    return found


def _match_brands(hints: tuple[str, ...]) -> list[CarBrand]:
    brands = list(CarBrand.objects.all())
    matched: list[CarBrand] = []
    seen: set[int] = set()
    for hint in hints:
        h = hint.casefold().strip()
        if not h:
            continue
        for b in brands:
            if b.pk in seen:
                continue
            blob = f"{b.name} {b.slug} {(b.sprite_key or '')}".casefold()
            if h in blob:
                seen.add(b.pk)
                matched.append(b)
    return matched


def _apply_brands(station: ServiceStation, seed: MasterSeed) -> None:
    if seed.brands_mode == "all":
        station.car_brands_all = True
        station.car_brands.clear()
        return

    station.car_brands_all = False
    all_brands = list(CarBrand.objects.all())

    if seed.brands_mode == "only":
        picked = _match_brands(seed.brands_only)
        station.car_brands.set(picked)
        return

    # all_except
    exclude_ids: set[int] = set()
    for hint in seed.brands_exclude:
        for b in _match_brands((hint,)):
            exclude_ids.add(b.pk)
    station.car_brands.set([b for b in all_brands if b.pk not in exclude_ids])


def _build_description(seed: MasterSeed) -> str:
    base = DESCRIPTIONS.get(seed.specialty_key) or DESCRIPTIONS["general"]
    parts = [base]
    if seed.specialty_label:
        parts.insert(0, f"Специализация: {seed.specialty_label}.")
    if seed.notes:
        parts.append(seed.notes)
    return " ".join(parts).strip()


def _district_for_city(city: str) -> District | None:
    return District.objects.filter(city_label__iexact=city).order_by("pk").first()


class Command(BaseCommand):
    help = "Импорт пакета мастеров/СТО/магазинов (bulk_masters_may2026): пользователи, карточки, пароли."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать план без записи в БД",
        )
        parser.add_argument(
            "--save-credentials",
            type=str,
            default="",
            help="Путь к файлу для сохранения телефон/пароль (UTF-8)",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Обновить карточку, если пользователь с таким телефоном уже есть",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        save_path = (options.get("save_credentials") or "").strip()
        update_existing: bool = options["update_existing"]

        credentials: list[str] = []
        created_users = updated_users = created_stations = skipped = 0

        for seed in MASTER_ENTRIES:
            if seed.skip:
                self.stdout.write(self.style.WARNING(f"ПРОПУСК: {seed.name} — {seed.skip_reason}"))
                skipped += 1
                continue

            if not (seed.phone or "").strip():
                self.stdout.write(self.style.WARNING(f"ПРОПУСК: {seed.name} — нет телефона"))
                skipped += 1
                continue

            try:
                phone = normalize_to_e164(seed.phone)
            except PhoneValidationError as e:
                self.stdout.write(self.style.ERROR(f"ОШИБКА телефона {seed.name}: {e}"))
                skipped += 1
                continue

            password = _make_password(seed, phone)
            desc = _build_description(seed)
            short = (seed.specialty_label or seed.name)[:500]

            if dry_run:
                self.stdout.write(
                    f"[dry-run] {seed.role:12} {phone} {seed.name} | пароль: {password} | {seed.city}"
                )
                credentials.append(f"{phone}\t{password}\t{seed.name}\t{seed.role}")
                continue

            with transaction.atomic():
                user = User.objects.filter(phone=phone).first()
                if user and not update_existing:
                    self.stdout.write(
                        self.style.WARNING(f"Уже есть пользователь {phone} — пропуск (используйте --update-existing)")
                    )
                    skipped += 1
                    continue

                if not user:
                    user = User.objects.create_user(
                        phone=phone,
                        password=password,
                        email=None,
                        is_active=True,
                        is_phone_verified=True,
                        business_role=seed.role,
                        business_role_chosen=True,
                        contact_phone=phone,
                        is_sto_owner=seed.role != User.BusinessRole.DRIVER,
                        sto_moderation_status=User.StoModerationStatus.APPROVED,
                        email_verified=True,
                    )
                    created_users += 1
                else:
                    user.business_role = seed.role
                    user.business_role_chosen = True
                    user.is_sto_owner = seed.role != User.BusinessRole.DRIVER
                    user.sto_moderation_status = User.StoModerationStatus.APPROVED
                    user.contact_phone = phone
                    user.is_active = True
                    user.is_phone_verified = True
                    user.set_password(password)
                    user.save()
                    updated_users += 1

                record_business_city(seed.city)
                district = _district_for_city(seed.city)

                if seed.role == User.BusinessRole.AUTOSHOP:
                    shop, shop_created = AutoShopProfile.objects.update_or_create(
                        owner=user,
                        defaults={
                            "name": seed.name,
                            "city_label": seed.city,
                            "address": seed.address,
                            "description": desc,
                            "contact_phone": phone,
                            "kind": seed.autoshop_kind or AutoShopProfile.Kind.SHOP,
                        },
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{'Создан' if shop_created else 'Обновлён'} магазин: {shop.name} ({phone})"
                        )
                    )
                else:
                    executor_kind = (
                        EXECUTOR_KIND_STO if seed.role == User.BusinessRole.AUTOSERVICE else EXECUTOR_KIND_PRIVATE
                    )
                    station = ServiceStation.objects.filter(owner=user).order_by("pk").first()
                    station_created = station is None
                    if station_created:
                        station = ServiceStation(owner=user)

                    station.name = seed.name
                    station.address = seed.address
                    station.executor_kind = executor_kind
                    station.is_active = True
                    station.is_verified = True
                    station.subscription_plan = SUBSCRIPTION_PLAN_FREE
                    station.subscription_paid_until = None
                    station.billing_blocked_at = None
                    station.district = district
                    station.contact_phone = phone
                    station.description = desc
                    station.description_short = short
                    station.tagline = (seed.specialty_label or "")[:220]
                    station.master_bio = desc
                    station.work_schedule_text = "По предварительной записи. Уточняйте время по телефону."
                    station.save()

                    cats = _find_categories(seed.specialty_key)
                    if cats:
                        station.categories.set(cats)
                        for cat in cats[:3]:
                            StationServiceOffer.objects.update_or_create(
                                station=station,
                                category=cat,
                                defaults={
                                    "service_title": cat.name,
                                    "price_from_rub": 1000,
                                    "note": "цена по согласованию",
                                },
                            )

                    _apply_brands(station, seed)

                    if station_created:
                        created_stations += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{'Создана' if station_created else 'Обновлена'} карточка: {station.name} ({phone})"
                        )
                    )

            credentials.append(f"{phone}\t{password}\t{seed.name}\t{seed.role}")

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                f"Готово: пользователей +{created_users}, обновлено {updated_users}, "
                f"станций/магазинов создано {created_stations}, пропущено {skipped}"
            )
        )

        if credentials:
            self.stdout.write(self.style.NOTICE("\n--- Логины (телефон) и пароли ---"))
            for line in credentials:
                phone, pwd, name, role = (line.split("\t") + ["", "", "", ""])[:4]
                self.stdout.write(f"{phone}  |  {pwd}  |  {name}")

        if save_path and credentials and not dry_run:
            path = Path(save_path)
            path.write_text(
                "phone\tpassword\tname\trole\n" + "\n".join(credentials) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(self.style.SUCCESS(f"Пароли сохранены: {path}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Режим dry-run: в БД ничего не записано."))
