from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import WorkingHours
from apps.stations.constants import (
    EXECUTOR_KIND_PRIVATE,
    EXECUTOR_KIND_STO,
    SUBSCRIPTION_PLAN_BASIC,
    SUBSCRIPTION_PLAN_FREE,
)
from apps.stations.models import (
    District,
    ServiceCategory,
    ServiceStation,
    StationServiceOffer,
    WorkBay,
)
from apps.users.models import User


@dataclass(frozen=True)
class SeedConfig:
    clients: int
    owners: int
    private_stations: int
    sto_stations: int
    categories: int
    offers_min: int
    offers_max: int
    with_locations: bool
    run_slot_generation: bool


def _phone_from_seq(seq: int) -> str:
    # +7999XXXXXXX (safe for demo; unique by seq)
    return f"+7999{seq:07d}"


def _rand_bool(p_true: float) -> bool:
    return random.random() < p_true


def _ensure_districts() -> list[District]:
    existing = list(District.objects.all())
    if existing:
        return existing
    city = "Владикавказ"
    names = [
        "Центр",
        "Северный",
        "Южный",
        "Затеречный",
        "Иристонский",
        "Октябрьский",
        "Пос. Спутник",
        "Пос. Редант",
    ]
    out = []
    for i, name in enumerate(names, start=1):
        out.append(District.objects.create(name=name, slug=f"dist-{i}", city_label=city))
    return out


def _ensure_categories(n: int) -> list[ServiceCategory]:
    existing = list(ServiceCategory.objects.order_by("name"))
    if len(existing) >= n:
        return existing
    base = [
        "Замена масла",
        "Диагностика",
        "Тормозная система",
        "Подвеска",
        "Шиномонтаж",
        "Развал‑схождение",
        "Электрика",
        "Кузовной ремонт",
        "Покраска",
        "Кондиционер",
        "ТО",
        "Замена колодок",
        "Замена свечей",
        "Замена ремня ГРМ",
        "Ремонт двигателя",
        "Ремонт КПП",
        "Ремонт выхлопа",
        "Замена фильтров",
    ]
    random.shuffle(base)
    need = max(0, n - len(existing))
    for title in base[:need]:
        slug = "svc-" + "".join(ch for ch in title.lower() if ch.isalnum())[:24]
        obj, _ = ServiceCategory.objects.get_or_create(name=title, defaults={"slug": slug})
        existing.append(obj)
    while len(existing) < n:
        i = len(existing) + 1
        title = f"Услуга #{i}"
        obj, _ = ServiceCategory.objects.get_or_create(name=title, defaults={"slug": f"svc-{i}"})
        existing.append(obj)
    return existing


def _create_users(*, kind: str, n: int) -> int:
    """
    kind: 'client' | 'owner'
    """
    created = 0
    base_seq = random.randint(3_000_000, 9_000_000)
    for i in range(n):
        phone = _phone_from_seq(base_seq + i)
        if User.objects.filter(phone=phone).exists():
            continue
        u = User(
            phone=phone,
            email=f"demo_{kind}_{base_seq + i}@example.com",
            is_active=True,
            is_phone_verified=True,
            is_sto_owner=(kind == "owner"),
        )
        u.set_password("demo12345")
        u.save()
        created += 1
    return created


def _maybe_set_location(st: ServiceStation) -> None:
    # Avoid hard dependency on GIS libs in environments where GEOS isn't available
    try:
        from django.contrib.gis.geos import Point
    except Exception:
        return
    lat = random.uniform(43.00, 43.08)
    lon = random.uniform(44.60, 44.74)
    st.location = Point(lon, lat, srid=4326)
    st.save(update_fields=["location"])


def _seed_station_offers(
    st: ServiceStation,
    categories: list[ServiceCategory],
    *,
    n_min: int,
    n_max: int,
) -> int:
    created = 0
    n = random.randint(n_min, n_max)
    cats = random.sample(categories, k=min(n, len(categories)))
    for c in cats:
        price = random.choice([800, 1200, 1500, 2000, 2500, 3500, 5000, 8000, 12000])
        title = "" if _rand_bool(0.55) else c.name
        note = random.choice(
            ["", "", "", "по записи", "в течение дня", "с гарантией", "с расходниками"]
        )
        _, was_created = StationServiceOffer.objects.get_or_create(
            station=st,
            category=c,
            defaults={"service_title": title, "price_from_rub": price, "note": note},
        )
        created += 1 if was_created else 0
    return created


def _seed_working_hours_for_bay(bay: WorkBay) -> int:
    created = 0
    for wd in range(7):
        if wd in (5, 6) and _rand_bool(0.35):
            continue
        opens = time(9, 0) if wd < 5 else time(10, 0)
        closes = time(19, 0) if wd < 5 else time(16, 0)
        _, was_created = WorkingHours.objects.get_or_create(
            bay=bay,
            weekday=wd,
            defaults={
                "opens_at": opens,
                "closes_at": closes,
                "slot_duration_minutes": random.choice([30, 30, 60]),
                "breaks": [{"start": "13:00", "end": "14:00"}] if wd < 5 else [],
            },
        )
        created += 1 if was_created else 0
    return created


class Command(BaseCommand):
    help = "Заполняет базу демо-данными. Пароль для созданных пользователей: demo12345"

    def add_arguments(self, parser):
        parser.add_argument("--clients", type=int, default=500)
        parser.add_argument("--owners", type=int, default=180)
        parser.add_argument(
            "--private", type=int, default=160, help="Частные мастера (ServiceStation)"
        )
        parser.add_argument("--sto", type=int, default=40, help="СТО (ServiceStation)")
        parser.add_argument("--categories", type=int, default=18)
        parser.add_argument("--offers-min", type=int, default=6)
        parser.add_argument("--offers-max", type=int, default=14)
        parser.add_argument(
            "--with-locations", action="store_true", help="Заполнить location (для карты)"
        )
        parser.add_argument(
            "--no-slot-generation", action="store_true", help="Не запускать генерацию слотов"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = SeedConfig(
            clients=int(options["clients"]),
            owners=int(options["owners"]),
            private_stations=int(options["private"]),
            sto_stations=int(options["sto"]),
            categories=int(options["categories"]),
            offers_min=int(options["offers_min"]),
            offers_max=int(options["offers_max"]),
            with_locations=bool(options["with_locations"]),
            run_slot_generation=not bool(options["no_slot_generation"]),
        )

        random.seed()
        today = timezone.localdate()

        districts = _ensure_districts()
        categories = _ensure_categories(cfg.categories)

        clients_created = _create_users(kind="client", n=cfg.clients)
        owners_created = _create_users(kind="owner", n=cfg.owners)

        owners_pool = list(User.objects.filter(is_sto_owner=True).order_by("id")[:1000])
        if not owners_pool:
            raise RuntimeError("Не удалось создать/найти владельцев СТО (owners_pool пуст).")

        def mk_station_name(kind: str, idx: int) -> str:
            if kind == EXECUTOR_KIND_PRIVATE:
                return random.choice(
                    [
                        f"Мастер {idx}",
                        f"Частный мастер {idx}",
                        f"Автомастер {idx}",
                        f"Слесарь {idx}",
                    ]
                )
            return random.choice(
                [
                    f"СТО «Гарант» #{idx}",
                    f"Автосервис «Профи» #{idx}",
                    f"СТО «Пит‑Стоп» #{idx}",
                    f"Сервис «Мотор» #{idx}",
                ]
            )

        def mk_address() -> str:
            streets = [
                "ул. Ленина",
                "ул. Коцоева",
                "пр. Мира",
                "ул. Ватутина",
                "ул. Маркова",
                "ул. Московская",
                "ул. Кирова",
            ]
            return f"{random.choice(streets)}, д. {random.randint(1, 220)}"

        stations_created = 0
        bays_created = 0
        wh_created = 0
        offers_created = 0

        def create_station(kind: str, idx: int) -> None:
            nonlocal stations_created, bays_created, wh_created, offers_created
            owner = random.choice(owners_pool)
            plan = SUBSCRIPTION_PLAN_BASIC if _rand_bool(0.55) else SUBSCRIPTION_PLAN_FREE
            paid_until = None
            if plan == SUBSCRIPTION_PLAN_BASIC:
                if _rand_bool(0.15):
                    paid_until = None
                elif _rand_bool(0.20):
                    paid_until = today - timedelta(days=random.randint(1, 25))
                else:
                    paid_until = today + timedelta(days=random.randint(5, 45))

            st = ServiceStation.objects.create(
                owner=owner,
                name=mk_station_name(kind, idx),
                address=mk_address(),
                description=random.choice(
                    [
                        "",
                        "Быстро и аккуратно. Запчасти по договорённости.",
                        "Диагностика и ремонт. Работаем честно.",
                        "Опытные мастера, гарантия на работы.",
                    ]
                ),
                description_short=random.choice(
                    [
                        "",
                        "Ремонт и обслуживание автомобилей",
                        "Диагностика и ТО",
                        "Шиномонтаж и подвеска",
                    ]
                ),
                work_schedule_text=random.choice(
                    [
                        "Пн–Пт 9:00–19:00, Сб 10:00–16:00",
                        "Пн–Сб 10:00–18:00",
                        "Ежедневно 9:00–20:00",
                        "",
                    ]
                ),
                executor_kind=kind,
                subscription_plan=plan,
                subscription_paid_until=paid_until,
                is_active=True,
                is_verified=_rand_bool(0.35),
                is_open_24_7=_rand_bool(0.07),
                district=random.choice(districts) if districts else None,
                certified_partner=_rand_bool(0.12),
                license_held=_rand_bool(0.08),
                has_parking=_rand_bool(0.35),
            )

            if cfg.with_locations and st.location is None and _rand_bool(0.75):
                try:
                    _maybe_set_location(st)
                except Exception:
                    pass

            st.categories.set(
                random.sample(categories, k=min(random.randint(2, 6), len(categories)))
            )

            offers_created += _seed_station_offers(
                st, categories, n_min=cfg.offers_min, n_max=cfg.offers_max
            )

            bay_n = 1 if kind == EXECUTOR_KIND_PRIVATE else random.choice([1, 2, 2, 3])
            for b in range(bay_n):
                bay = WorkBay.objects.create(station=st, name=f"Пост {b + 1}")
                bays_created += 1
                wh_created += _seed_working_hours_for_bay(bay)

            stations_created += 1

        for i in range(1, cfg.private_stations + 1):
            create_station(EXECUTOR_KIND_PRIVATE, i)
        for i in range(1, cfg.sto_stations + 1):
            create_station(EXECUTOR_KIND_STO, i)

        self.stdout.write(self.style.SUCCESS("Seed completed."))
        self.stdout.write(
            "Created: "
            f"clients={clients_created}, owners={owners_created}, "
            f"stations={stations_created} "
            f"(private={cfg.private_stations}, sto={cfg.sto_stations}), "
            f"offers={offers_created}, bays={bays_created}, working_hours={wh_created}"
        )
        self.stdout.write("Password for created users: demo12345")

        if cfg.run_slot_generation:
            from apps.bookings.slot_generation import run_generate_weekly_slots

            n = run_generate_weekly_slots()
            self.stdout.write(self.style.SUCCESS(f"Generated TimeSlot rows: {n}"))
