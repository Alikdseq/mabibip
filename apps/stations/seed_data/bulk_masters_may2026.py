"""
Пакетное добавление мастеров/автосервисов/магазинов (май 2026).
Используется management command: import_masters_batch
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["master", "autoservice", "autoshop"]
BrandsMode = Literal["all", "all_except", "only"]


@dataclass(frozen=True)
class MasterSeed:
    """Одна запись для импорта."""

    name: str  # название карточки / бизнеса
    phone: str  # 10–11 цифр, 8… или +7…
    city: str
    address: str
    role: Role = "master"
    specialty_key: str = "general"
    specialty_label: str = ""  # для описания
    brands_mode: BrandsMode = "all"
    brands_exclude: tuple[str, ...] = ()
    brands_only: tuple[str, ...] = ()
    password: str | None = None  # если None — сгенерировать
    notes: str = ""  # доп. в описание (ограничения)
    autoshop_kind: str = "shop"  # shop | dismantle | dealer
    skip: bool = False
    skip_reason: str = ""


# fmt: off
MASTER_ENTRIES: list[MasterSeed] = [
    MasterSeed(
        name="Махир — электрика и диагностика",
        phone="89888710762",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 10",
        specialty_key="electric",
        specialty_label="Электрика, диагностика",
        brands_mode="all_except",
        brands_exclude=("bmw", "mercedes", "мерседес"),
    ),
    MasterSeed(
        name="Саркиз — электрика",
        phone="89891334028",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 10",
        specialty_key="electric",
        specialty_label="Электрика",
        brands_mode="all_except",
        brands_exclude=("volga", "волга", "газ-21"),
    ),
    MasterSeed(
        name="Вова — жестяные работы",
        phone="89094737071",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 10",
        specialty_key="bodywork",
        specialty_label="Жестяные работы",
        notes="Заплатки не выполняем. Старые автомобили — по согласованию.",
    ),
    MasterSeed(
        name="Руха — маляр",
        phone="9688165395",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 10",
        specialty_key="paint",
        specialty_label="Малярные работы, покраска",
    ),
    MasterSeed(
        name="Эдуард — ремонт пластика",
        phone="89604030606",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 10",
        specialty_key="plastic",
        specialty_label="Сборка, разборка, пайка пластика",
    ),
    MasterSeed(
        name="Аслан — диагностика и ремонт (Сармат)",
        phone="89187046404",
        city="Беслан",
        address="г. Беслан, пер. Крайний, 1, автосервис «Сармат», бокс 1",
        specialty_key="diagnostic_full",
        specialty_label="Диагностика, ремонт ходовой, двигателя и КПП",
        notes="Иномарки и отечественные авто; Lada Vesta — специализация.",
    ),
    MasterSeed(
        name="Виталик Скаев — диагностика и ремонт (Сармат)",
        phone="89280656516",
        city="Беслан",
        address="г. Беслан, пер. Крайний, 1, автосервис «Сармат», бокс 1",
        specialty_key="diagnostic_full",
        specialty_label="Диагностика, ремонт ходовой, двигателя и КПП",
        notes="Иномарки и отечественные авто; Lada Vesta.",
    ),
    MasterSeed(
        name="Алан — детейлинг",
        phone="89897461664",
        city="Беслан",
        address="г. Беслан, пер. Крайний, 1, бокс справа",
        specialty_key="detailing",
        specialty_label="Детейлинг",
    ),
    MasterSeed(
        name="Mauardon — система охлаждения",
        phone="89280749493",
        city="Беслан",
        address="г. Беслан, пер. Крайний, 2",
        role="autoservice",
        specialty_key="cooling",
        specialty_label="Аппаратная система охлаждения",
        password="Sarmat777",
    ),
    MasterSeed(
        name="Марат — ремонт двигателей и ходовой",
        phone="89284890304",
        city="Беслан",
        address="г. Беслан, ул. Цаликова, 2",
        specialty_key="engine",
        specialty_label="Ремонт двигателей, ходовой, тормозных колодок",
    ),
    MasterSeed(
        name="Аслан — частный мастер",
        phone="89280711701",
        city="Беслан",
        address="г. Беслан",
        specialty_key="general",
        specialty_label="Ремонт и обслуживание автомобилей",
    ),
    MasterSeed(
        name="Тамик — частный мастер",
        phone="89388642568",
        city="Беслан",
        address="г. Беслан",
        specialty_key="general",
        specialty_label="Ремонт и обслуживание автомобилей",
    ),
    MasterSeed(
        name="Вова — установка ГБО",
        phone="89888327932",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="gbo",
        specialty_label="Установка и обслуживание ГБО",
    ),
    MasterSeed(
        name="Сослан — ремонт Range Rover",
        phone="89188200769",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="land_rover",
        specialty_label="Ремонт и обслуживание Range Rover / Land Rover",
        brands_mode="only",
        brands_only=("range rover", "land rover", "рендж", "ленд ровер"),
    ),
    MasterSeed(
        name="Жорик — разборка Mercedes",
        phone="89284901277",
        city="Владикавказ",
        address="г. Владикавказ, ул. 1-я Промышленная",
        specialty_key="dismantle",
        specialty_label="Разборка Mercedes-Benz",
        brands_mode="only",
        brands_only=("mercedes", "мерседес"),
    ),
    MasterSeed(
        name="Марат — разборка и ремонт иномарок",
        phone="89888704815",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="dismantle",
        specialty_label="Разборка и ремонт иномарок",
    ),
    MasterSeed(
        name="Марина — подбор краски",
        phone="89064947789",
        city="Владикавказ",
        address="г. Владикавказ, На Барсе",
        specialty_key="paint_match",
        specialty_label="Подбор автомобильной краски",
    ),
    MasterSeed(
        name="Нодар — маляр",
        phone="89284803089",
        city="Владикавказ",
        address="г. Владикавказ, На Пианинке",
        specialty_key="paint",
        specialty_label="Малярные работы, покраска",
    ),
    MasterSeed(
        name="Паша — пайка бамперов",
        phone="89888751150",
        city="Владикавказ",
        address="г. Владикавказ, ул. Доватора",
        specialty_key="plastic",
        specialty_label="Пайка и ремонт бамперов",
    ),
    MasterSeed(
        name="Роберт — ремонт глушителей",
        phone="89284971482",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="exhaust",
        specialty_label="Ремонт и замена глушителей",
    ),
    MasterSeed(
        name="Руслан — ремонт и диагностика",
        phone="89188244377",
        city="Владикавказ",
        address="г. Владикавказ, На Барсе",
        specialty_key="diagnostic_full",
        specialty_label="Ремонт и диагностика иномарок",
    ),
    MasterSeed(
        name="Сергей — б/у шины",
        phone="89188233470",
        city="Владикавказ",
        address="г. Владикавказ, Бесланское шоссе",
        role="autoshop",
        specialty_key="tires_shop",
        specialty_label="Продажа б/у шин и дисков",
        autoshop_kind="shop",
    ),
    MasterSeed(
        name="Тимур — жестяные работы",
        phone="89188346095",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="bodywork",
        specialty_label="Жестяные работы",
    ),
    MasterSeed(
        name="Славик — жестянка ГАЗель",
        phone="89188229515",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 3",
        specialty_key="bodywork",
        specialty_label="Жестяные работы и регулировка ГАЗель",
        brands_mode="only",
        brands_only=("газель", "gazelle", "gaz"),
        notes="Специализация на коммерческих ГАЗель.",
    ),
    MasterSeed(
        name="Славик — жестяные работы",
        phone="89034837775",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 2",
        specialty_key="bodywork",
        specialty_label="Жестяные работы",
    ),
    MasterSeed(
        name="Визитка МТС — автозапчасти",
        phone="",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 4",
        role="autoshop",
        specialty_key="parts_shop",
        specialty_label="Магазин автозапчастей",
        skip=True,
        skip_reason="не указан телефон — добавьте номер и запустите снова",
    ),
    MasterSeed(
        name="Валера — радиаторы и диски",
        phone="89280721440",
        city="Владикавказ",
        address="г. Владикавказ, ул. Гвардейская, 4",
        specialty_key="radiator",
        specialty_label="Ремонт радиаторов, дисков, топливных баков (грузовики)",
        notes="WhatsApp: 89888732671",
    ),
    MasterSeed(
        name="Олег — детейлинг",
        phone="89888346664",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 12А",
        specialty_key="detailing",
        specialty_label="Детейлинг",
    ),
    MasterSeed(
        name="Георгий — диагностика и ТО",
        phone="89094774748",
        city="Владикавказ",
        address="г. Владикавказ, Карцинское шоссе, 12А",
        specialty_key="diagnostic_grm",
        specialty_label="Диагностика, ремонт ходовой, ГРМ, обслуживание подкапотного пространства",
        brands_mode="all_except",
        brands_exclude=("bmw", "mercedes", "мерседес"),
        password="georgi987",
    ),
]
# fmt: on
