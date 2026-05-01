from __future__ import annotations

import secrets
from collections.abc import Iterable

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils.text import slugify

from apps.stations.models import CarBrand
from apps.stations.geocoding import geocode_address_to_point


class AutoShopProfile(models.Model):
    """Публичная страница магазина/разборки (SEO URL /shops/<slug>/)."""

    class Kind(models.TextChoices):
        SHOP = "shop", "Автомагазин"
        DISMANTLE = "dismantle", "Разборка"
        DEALER = "dealer", "Автосалон"

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="autoshop_profile",
        verbose_name="Владелец",
    )
    name = models.CharField("Название", max_length=200)
    kind = models.CharField("Тип", max_length=16, choices=Kind.choices, default=Kind.SHOP, db_index=True)
    slug = models.SlugField("Слаг", max_length=220, unique=True, db_index=True)
    city_label = models.CharField("Город", max_length=120, blank=True, default="")
    address = models.CharField("Адрес", max_length=500, blank=True, default="")
    location = PointField(
        "Точка на карте (WGS 84)",
        srid=4326,
        null=True,
        blank=True,
        help_text="Координаты для карты. При включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
    )
    description = models.TextField("Описание", blank=True, default="")
    contact_phone = models.CharField("Телефон", max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Автомагазин/разборка/автосалон"
        verbose_name_plural = "Автомагазины/разборки/автосалоны"
        ordering = ["name", "pk"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "shop"
            slug = base
            n = 0
            qs = AutoShopProfile.objects.exclude(pk=self.pk) if self.pk else AutoShopProfile.objects.all()
            while qs.filter(slug=slug).exists():
                n += 1
                suffix = f"-{n}"
                slug = f"{base[: 200 - len(suffix)]}{suffix}"
            self.slug = slug

        # Автогеокодинг: только если включён флаг и координат ещё нет.
        if (
            getattr(settings, "GEOCODING_ENABLED", False)
            and (self.address or "").strip()
            and self.location is None
        ):
            pt = geocode_address_to_point(self.address)
            if pt is not None:
                self.location = pt
        super().save(*args, **kwargs)


class AutoShopBranch(models.Model):
    """Филиал автомагазина/разборки/автосалона (несколько точек у одного профиля)."""

    shop = models.ForeignKey(
        AutoShopProfile,
        on_delete=models.CASCADE,
        related_name="branches",
        verbose_name="Магазин",
    )
    name = models.CharField("Название филиала", max_length=200, blank=True, default="")
    city_label = models.CharField("Город", max_length=120, blank=True, default="")
    address = models.CharField("Адрес", max_length=500, blank=True, default="")
    location = PointField(
        "Точка на карте (WGS 84)",
        srid=4326,
        null=True,
        blank=True,
        help_text="Координаты для карты. При включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
    )
    contact_phone = models.CharField("Телефон", max_length=32, blank=True, default="")
    work_hours = models.CharField("Часы работы", max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Филиал автомагазина"
        verbose_name_plural = "Филиалы автомагазинов"
        ordering = ["shop_id", "name", "pk"]

    def __str__(self) -> str:
        base = (self.name or "").strip()
        if base:
            return base
        parts = [p for p in [self.city_label, self.address] if (p or "").strip()]
        return " · ".join(parts)[:140] or f"Филиал #{self.pk}"

    def save(self, *args, **kwargs):
        # Автогеокодинг: только если включён флаг и координат ещё нет.
        if (
            getattr(settings, "GEOCODING_ENABLED", False)
            and (self.address or "").strip()
            and self.location is None
        ):
            pt = geocode_address_to_point(self.address)
            if pt is not None:
                self.location = pt
        super().save(*args, **kwargs)


class PartCategory(models.Model):
    name = models.CharField("Раздел запчастей", max_length=120, unique=True)
    slug = models.SlugField("Слаг", max_length=140, unique=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        verbose_name = "Раздел запчастей"
        verbose_name_plural = "Разделы запчастей"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class AdKind(models.TextChoices):
    PART = "part", "Автозапчасть"
    CAR = "car", "Автомобиль"


class AdCondition(models.TextChoices):
    NEW = "new", "Новая"
    USED = "used", "Б/у"


class CarTransmission(models.TextChoices):
    MT = "mt", "Механика"
    AT = "at", "Автомат"
    CVT = "cvt", "Вариатор"
    AMT = "amt", "Робот"
    OTHER = "other", "Другое"


class CarFuel(models.TextChoices):
    PETROL = "petrol", "Бензин"
    DIESEL = "diesel", "Дизель"
    GAS = "gas", "Газ (ГБО)"
    HYBRID = "hybrid", "Гибрид"
    ELECTRIC = "electric", "Электро"
    OTHER = "other", "Другое"


class CarDrive(models.TextChoices):
    FWD = "fwd", "Передний"
    RWD = "rwd", "Задний"
    AWD = "awd", "Полный"
    OTHER = "other", "Другое"


class CarBodyType(models.TextChoices):
    SEDAN = "sedan", "Седан"
    HATCHBACK = "hatchback", "Хэтчбек"
    WAGON = "wagon", "Универсал"
    SUV = "suv", "Внедорожник / кроссовер"
    COUPE = "coupe", "Купе"
    CONVERTIBLE = "convertible", "Кабриолет"
    VAN = "van", "Минивэн"
    PICKUP = "pickup", "Пикап"
    LIFTBACK = "liftback", "Лифтбек"
    OTHER = "other", "Другое"


class CarSteering(models.TextChoices):
    LEFT = "left", "Левый"
    RIGHT = "right", "Правый"


class Ad(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ads",
        verbose_name="Автор",
    )
    shop = models.ForeignKey(
        AutoShopProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        verbose_name="Магазин",
    )
    kind = models.CharField("Тип", max_length=16, choices=AdKind.choices, db_index=True)
    title = models.CharField("Заголовок", max_length=200)
    price = models.PositiveIntegerField("Цена", default=0)
    city_label = models.CharField("Город", max_length=120, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    is_published = models.BooleanField("Опубликовано", default=True, db_index=True)

    class UnpublishReason(models.TextChoices):
        SOLD = "sold", "Продал(а)"
        NOT_AVAILABLE = "not_available", "Нет в наличии"
        CHANGED_MIND = "changed_mind", "Передумал(а)"
        WRONG_PRICE = "wrong_price", "Ошибка в цене"
        OTHER = "other", "Другая причина"

    unpublished_at = models.DateTimeField("Снято с публикации", null=True, blank=True, db_index=True)
    unpublish_reason = models.CharField(
        "Причина снятия",
        max_length=32,
        choices=UnpublishReason.choices,
        blank=True,
        default="",
        db_index=True,
    )
    unpublish_reason_text = models.CharField("Комментарий к причине", max_length=300, blank=True, default="")

    class ModerationStatus(models.TextChoices):
        OK = "ok", "OK"
        PENDING = "pending", "На проверке"
        HIDDEN = "hidden", "Скрыто"

    moderation_status = models.CharField(
        "Модерация",
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.OK,
        db_index=True,
    )
    moderation_reason = models.CharField("Причина модерации", max_length=300, blank=True, default="")
    view_count = models.PositiveIntegerField(
        "Просмотры",
        default=0,
        db_index=True,
        help_text="Счётчик показов карточки; один зачёт не чаще одного раза за сессию браузера.",
    )

    # parts
    part_category = models.ForeignKey(
        PartCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        verbose_name="Раздел запчастей",
    )
    part_brand = models.ForeignKey(
        CarBrand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="part_ads",
        verbose_name="Марка авто (для запчасти)",
    )
    condition = models.CharField(
        "Состояние",
        max_length=16,
        choices=AdCondition.choices,
        blank=True,
        default="",
    )

    # cars
    car_brand = models.ForeignKey(
        CarBrand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="car_ads",
        verbose_name="Марка авто",
    )
    car_model = models.CharField("Модель", max_length=120, blank=True, default="")
    car_year = models.PositiveSmallIntegerField("Год", null=True, blank=True)
    car_mileage_km = models.PositiveIntegerField("Пробег, км", null=True, blank=True)
    car_generation = models.CharField(
        "Поколение / рестайлинг",
        max_length=120,
        blank=True,
        default="",
        help_text="Например: III рестайлинг, X167 — по желанию.",
    )
    car_engine_l = models.DecimalField(
        "Объём двигателя, л",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Например: 2.0 (литры).",
    )
    car_power_hp = models.PositiveSmallIntegerField(
        "Мощность, л.с.",
        null=True,
        blank=True,
    )
    car_transmission = models.CharField(
        "Коробка передач",
        max_length=16,
        choices=CarTransmission.choices,
        blank=True,
        default="",
        db_index=True,
    )
    car_fuel = models.CharField(
        "Топливо",
        max_length=16,
        choices=CarFuel.choices,
        blank=True,
        default="",
        db_index=True,
    )
    car_drive = models.CharField(
        "Привод",
        max_length=16,
        choices=CarDrive.choices,
        blank=True,
        default="",
        db_index=True,
    )
    car_body_type = models.CharField(
        "Тип кузова",
        max_length=20,
        choices=CarBodyType.choices,
        blank=True,
        default="",
        db_index=True,
    )
    car_color = models.CharField("Цвет", max_length=64, blank=True, default="")
    car_steering = models.CharField(
        "Руль",
        max_length=8,
        choices=CarSteering.choices,
        blank=True,
        default="",
    )
    car_vin = models.CharField(
        "VIN",
        max_length=32,
        blank=True,
        default="",
        help_text="Необязательно. На сайте показывается частично.",
    )
    car_owners_count = models.PositiveSmallIntegerField(
        "Число владельцев по ПТС",
        null=True,
        blank=True,
    )
    car_not_crashed = models.BooleanField(
        "Не битый / не участвовал в ДТП",
        null=True,
        blank=True,
        help_text="Пусто — не указано.",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["kind", "is_published", "-created_at"]),
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["shop", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} #{self.pk}"

    def car_specs_line(self) -> str:
        """Одна строка ключевых характеристик авто для списка объявлений."""
        if self.kind != AdKind.CAR:
            return ""
        chunks: list[str] = []
        if self.car_engine_l is not None:
            t = format(self.car_engine_l, "f").rstrip("0").rstrip(".") or "0"
            chunks.append(f"{t} л")
        if self.car_transmission:
            chunks.append(self.get_car_transmission_display())
        if self.car_power_hp:
            chunks.append(f"{self.car_power_hp} л.с.")
        if self.car_body_type:
            chunks.append(self.get_car_body_type_display())
        if self.car_drive:
            chunks.append(self.get_car_drive_display())
        if self.car_fuel:
            chunks.append(self.get_car_fuel_display())
        return ", ".join(chunks)

    def car_card_headline(self) -> str:
        """Заголовок карточки в стиле витрины: марка, модель, мотор/КПП, год, пробег."""
        if self.kind != AdKind.CAR:
            return self.title
        brand_model = " ".join(
            x for x in (self.car_brand.name if self.car_brand else "", (self.car_model or "").strip()) if x
        ).strip()
        if not brand_model:
            brand_model = self.title.strip() or self.title

        trans_short = ""
        if self.car_transmission:
            trans_short = {
                CarTransmission.MT: "MT",
                CarTransmission.AT: "AT",
                CarTransmission.CVT: "CVT",
                CarTransmission.AMT: "AMT",
                CarTransmission.OTHER: "",
            }.get(self.car_transmission, "") or self.get_car_transmission_display()

        left_bits: list[str] = []
        if self.car_engine_l is not None:
            t = format(self.car_engine_l, "f").rstrip("0").rstrip(".") or "0"
            left_bits.append(t)
        if trans_short:
            left_bits.append(trans_short)
        if self.car_power_hp:
            left_bits.append(f"({self.car_power_hp} л.с.)")

        head = brand_model
        if left_bits:
            head = f"{head} {' '.join(left_bits)}".strip()

        tail: list[str] = []
        if self.car_year:
            tail.append(str(self.car_year))
        if self.car_mileage_km is not None:
            tail.append(f"{self.car_mileage_km} км")

        if tail:
            head = f"{head}, {', '.join(tail)}"
        return head.strip() or self.title


class AdCallProxy(models.Model):
    """
    Добавочный код для звонка через публичный «подменный» номер платформы.
    Номер и переадресация настраиваются в телефонии; здесь только стабильный код на объявление.
    """

    ad = models.OneToOneField(
        Ad,
        on_delete=models.CASCADE,
        related_name="call_proxy",
        verbose_name="Объявление",
    )
    extension = models.CharField(
        "Добавочный (DTMF)",
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Подменный звонок (добавочный)"
        verbose_name_plural = "Подменные звонки (добавочные)"

    def __str__(self) -> str:
        return f"AdCallProxy ad={self.ad_id} ext={self.extension}"

    def assign_extension(self) -> None:
        if self.extension:
            return
        for _ in range(80):
            ext = "".join(secrets.choice("0123456789") for _ in range(6))
            if not AdCallProxy.objects.filter(extension=ext).exclude(pk=self.pk).exists():
                self.extension = ext
                self.save(update_fields=["extension", "updated_at"])
                return
        raise RuntimeError("Не удалось сгенерировать уникальный добавочный код.")


def ad_photo_upload_to(instance, filename: str) -> str:
    return f"ads/{instance.ad_id or 0}/{filename}"


class AdPhoto(models.Model):
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="photos", verbose_name="Объявление")
    image = models.ImageField(
        "Фото",
        upload_to=ad_photo_upload_to,
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp"),
                message="Допустимы только изображения JPG, PNG или WEBP.",
            )
        ],
    )
    order = models.PositiveSmallIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        verbose_name = "Фото объявления"
        verbose_name_plural = "Фото объявлений"
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return f"AdPhoto ad={self.ad_id}"


class PhoneRevealLog(models.Model):
    """Факт раскрытия телефона продавца по кнопке (антифрод лимиты и аудит)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_reveal_logs",
        verbose_name="Пользователь",
    )
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="phone_reveal_logs",
        verbose_name="Объявление",
    )
    revealed_at = models.DateTimeField("Раскрыто", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "раскрытие телефона"
        verbose_name_plural = "раскрытия телефонов"
        ordering = ["-revealed_at", "-pk"]
        indexes = [
            models.Index(fields=["user", "-revealed_at"], name="clsfd_reveal_user_time"),
            models.Index(fields=["ad", "-revealed_at"], name="clsfd_reveal_ad_time"),
        ]


class AdReport(models.Model):
    """Жалоба на объявление (авто-скрытие при пороге)."""

    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="Объявление",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ad_reports",
        verbose_name="Кто пожаловался",
    )
    reason = models.CharField("Причина", max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "жалоба на объявление"
        verbose_name_plural = "жалобы на объявления"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["ad", "reported_by"], name="uniq_ad_report_ad_user"),
        ]
        indexes = [
            models.Index(fields=["ad", "-created_at"], name="clsfd_report_ad_time"),
            models.Index(fields=["reported_by", "-created_at"], name="clsfd_report_user_time"),
        ]


class PhoneChangeLog(models.Model):
    """Аудит смены телефона в профиле пользователя (антифрод)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_change_logs",
        verbose_name="Пользователь",
    )
    old_phone = models.CharField("Старый телефон", max_length=32, blank=True, default="")
    new_phone = models.CharField("Новый телефон", max_length=32, blank=True, default="")
    changed_at = models.DateTimeField("Изменено", auto_now_add=True, db_index=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        verbose_name = "смена телефона"
        verbose_name_plural = "смены телефона"
        ordering = ["-changed_at", "-pk"]
        indexes = [
            models.Index(fields=["user", "-changed_at"], name="clsfd_phonechg_user_time"),
        ]


class ImageHash(models.Model):
    """Perceptual hash фото объявления для поиска дубликатов между аккаунтами."""

    photo = models.OneToOneField(
        AdPhoto,
        on_delete=models.CASCADE,
        related_name="image_hash",
        verbose_name="Фото",
    )
    phash = models.CharField("pHash", max_length=32, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "хэш изображения"
        verbose_name_plural = "хэши изображений"
        ordering = ["-created_at", "-pk"]


class FavoriteAd(models.Model):
    """Избранное объявлений (в ЛК клиента)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_ads",
        verbose_name="Пользователь",
    )
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="Объявление",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Избранное объявление"
        verbose_name_plural = "Избранные объявления"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["user", "ad"], name="uniq_favorite_ad_user_ad"),
        ]


class FavoriteShop(models.Model):
    """Избранное автомагазинов/разборок/автосалонов (в ЛК клиента)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_shops",
        verbose_name="Пользователь",
    )
    shop = models.ForeignKey(
        AutoShopProfile,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="Магазин",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Избранный автомагазин"
        verbose_name_plural = "Избранные автомагазины"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["user", "shop"], name="uniq_favorite_shop_user_shop"),
        ]


class AdCallClickEvent(models.Model):
    """Факт нажатия «Позвонить» авторизованным покупателем (без АТС на старте)."""

    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="call_click_events",
        verbose_name="Объявление",
    )
    ad_kind = models.CharField("Тип объявления", max_length=16, choices=AdKind.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classified_ad_call_clicks",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Клик «Позвонить» (объявление)"
        verbose_name_plural = "Клики «Позвонить» (объявления)"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["ad_kind", "-created_at"], name="clfdc_adcclk_kind_crt"),
        ]


class SellerReviewModerationStatus(models.TextChoices):
    """Согласовано по значениям с apps.reviews.ModerationStatus (общие статусы в БД)."""

    OK = "ok", "OK"
    UNDER_REVIEW = "under_review", "На проверке"
    HIDDEN = "hidden", "Скрыт"


class SellerReview(models.Model):
    """Отзыв покупателя о продавце в разделе объявлений (не путать с отзывом по записи в СТО)."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classifieds_seller_reviews_written",
        verbose_name="Автор отзыва",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="classifieds_seller_reviews_received",
        verbose_name="Продавец",
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField("Текст", blank=True, default="")
    moderation_status = models.CharField(
        "Статус модерации",
        max_length=20,
        choices=SellerReviewModerationStatus.choices,
        default=SellerReviewModerationStatus.OK,
        db_index=True,
    )
    moderation_reason = models.CharField("Причина модерации", max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Отзыв о продавце (объявления)"
        verbose_name_plural = "Отзывы о продавцах (объявления)"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["author", "seller"],
                name="classifieds_sellerreview_author_seller_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["seller", "moderation_status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"★{self.rating} — {self.author_id} → {self.seller_id}"


def seller_review_done_owner_ids_for_user(user, owner_pks: Iterable[int]) -> set[int]:
    """ID продавцов (User.pk), для которых у пользователя уже есть SellerReview."""
    if not getattr(user, "is_authenticated", False):
        return set()
    pks = {pk for pk in owner_pks if pk is not None}
    if not pks:
        return set()
    return set(
        SellerReview.objects.filter(author=user, seller_id__in=pks).values_list("seller_id", flat=True)
    )

