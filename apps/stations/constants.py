"""Подписки и каталог (шаг 0.4.1, 0.4.4)."""

SUBSCRIPTION_PLAN_FREE = "free"
SUBSCRIPTION_PLAN_BASIC = "basic"

SUBSCRIPTION_PLAN_CHOICES = (
    (SUBSCRIPTION_PLAN_FREE, "Free"),
    (SUBSCRIPTION_PLAN_BASIC, "Basic"),
)

# Окно выбора даты записи на карточке СТО и горизонт «ближайшего слота» в каталоге (дней от сегодня).
CATALOG_DAY_RANGE = 7

EXECUTOR_KIND_STO = "sto"
EXECUTOR_KIND_PRIVATE = "private"
EXECUTOR_KIND_CHOICES = (
    (EXECUTOR_KIND_STO, "СТО / автосервис"),
    (EXECUTOR_KIND_PRIVATE, "Частный мастер"),
)

ADDRESS_PUBLIC_FULL = "full"
ADDRESS_PUBLIC_DISTRICT = "district_only"
ADDRESS_PUBLIC_AFTER_BOOKING = "hidden_until_booking"
ADDRESS_PUBLIC_MODE_CHOICES = (
    (ADDRESS_PUBLIC_FULL, "Полный адрес"),
    (ADDRESS_PUBLIC_DISTRICT, "Только район"),
    (ADDRESS_PUBLIC_AFTER_BOOKING, "Точный адрес после записи"),
)
