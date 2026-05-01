from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from simple_history.models import HistoricalRecords

from .constants import (
    ADDRESS_PUBLIC_MODE_CHOICES,
    ADDRESS_PUBLIC_FULL,
    EXECUTOR_KIND_CHOICES,
    EXECUTOR_KIND_STO,
    SUBSCRIPTION_PLAN_CHOICES,
    SUBSCRIPTION_PLAN_FREE,
)
from .managers import ServiceStationManager
from .visibility import station_is_visible


class ServiceStation(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_stations",
        verbose_name="Владелец",
    )
    parent_station = models.ForeignKey(
        "stations.ServiceStation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="masters",
        verbose_name="Сервис-родитель (для мастеров)",
        help_text="Если заполнено — это мастер автосервиса и отображается в каталоге как отдельный исполнитель.",
    )
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=220, unique=True, db_index=True)
    address = models.CharField("Адрес", max_length=500)
    location = PointField(
        "Точка на карте (WGS 84)",
        srid=4326,
        null=True,
        blank=True,
        help_text="Координаты для геопоиска. Можно задать вручную; при включённом GEOCODING_ENABLED заполняется из адреса через Nominatim.",
    )
    description = models.TextField("Описание", blank=True)
    categories = models.ManyToManyField(
        "stations.ServiceCategory",
        verbose_name="Категории услуг",
        related_name="stations",
        blank=True,
    )
    service_sections = models.ManyToManyField(
        "stations.ServiceSection",
        verbose_name="Разделы услуг (быстрый выбор)",
        related_name="stations",
        blank=True,
        help_text="Если выбрать разделы, станция будет попадать в фильтр каталога по разделу даже без точечных категорий.",
    )
    car_brands = models.ManyToManyField(
        "stations.CarBrand",
        verbose_name="Марки авто (с которыми работает)",
        related_name="stations",
        blank=True,
    )
    car_brands_all = models.BooleanField(
        "Все марки",
        default=False,
        help_text="Если включено — карточка участвует в каталоге при любом фильтре по марке.",
        db_index=True,
    )
    subscription_plan = models.CharField(
        "Тариф",
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default=SUBSCRIPTION_PLAN_FREE,
        help_text=(
            "Free — в каталоге без проверки оплаты. "
            "Basic — в каталоге только при заполненной дате «оплачено до» не раньше текущего дня."
        ),
    )
    subscription_paid_until = models.DateField(
        "Подписка оплачена до",
        null=True,
        blank=True,
        help_text=(
            "Для Basic: последний день включительно показа в каталоге; "
            "пустое значение — не показываем. Для Free поле не используется."
        ),
    )
    is_active = models.BooleanField(
        "Активна",
        default=True,
        help_text="Выключенные СТО не отображаются в публичном каталоге.",
    )
    billing_blocked_at = models.DateTimeField(
        "Заблокировано биллингом",
        null=True,
        blank=True,
        help_text="Если заполнено — СТО скрыта из каталога и не принимает новые заявки (фаза F4).",
    )
    executor_kind = models.CharField(
        "Тип исполнителя",
        max_length=20,
        choices=EXECUTOR_KIND_CHOICES,
        default=EXECUTOR_KIND_STO,
        db_index=True,
    )
    is_verified = models.BooleanField(
        "Проверен",
        default=False,
        help_text="Плашка «Проверен» в каталоге (модерация вручную).",
        db_index=True,
    )
    is_open_24_7 = models.BooleanField("Круглосуточно", default=False, db_index=True)
    district = models.ForeignKey(
        "stations.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stations",
        verbose_name="Район / локация",
    )
    amenity_wifi = models.BooleanField("Wi‑Fi для клиентов", default=False)
    amenity_coffee = models.BooleanField("Кофе / чай", default=False)
    amenity_cards = models.BooleanField("Оплата картой", default=False)
    amenity_tow = models.BooleanField("Эвакуатор / эвакуация", default=False)
    amenity_legal = models.BooleanField("Работа с юрлицами", default=False)
    contact_phone = models.CharField(
        "Телефон для клиентов (E.164)",
        max_length=20,
        blank=True,
        help_text="Публичный номер. Если пусто — для авторизованных показывается телефон владельца.",
    )
    whatsapp_phone = models.CharField(
        "WhatsApp (номер, E.164)",
        max_length=20,
        blank=True,
        help_text="Для ссылки wa.me; можно совпадать с contact_phone.",
    )
    telegram_username = models.CharField("Telegram (ник без @)", max_length=64, blank=True)
    website = models.URLField("Сайт", blank=True)
    vk_url = models.URLField("ВКонтакте", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    ogrn = models.CharField("ОГРН / ОГРНИП", max_length=15, blank=True)
    description_short = models.CharField(
        "Краткое описание (до 500 симв.)",
        max_length=500,
        blank=True,
        help_text="Для шапки и SEO; основное описание ниже.",
    )
    work_schedule_text = models.TextField(
        "График работы (текст)",
        blank=True,
        help_text="Напр.: Пн–Пт 9:00–20:00, Сб 10:00–18:00, Вс — выходной.",
    )
    certified_partner = models.BooleanField("Сертифицированный сервис (плашка)", default=False)
    license_held = models.BooleanField("Лицензия / документы на проверке у админа", default=False)
    has_parking = models.BooleanField("Парковка для клиентов", default=False)
    address_public_mode = models.CharField(
        "Как показывать адрес",
        max_length=30,
        choices=ADDRESS_PUBLIC_MODE_CHOICES,
        default=ADDRESS_PUBLIC_FULL,
    )
    tagline = models.CharField(
        "Специализация / слоган (частный мастер)",
        max_length=220,
        blank=True,
    )
    experience_years = models.PositiveSmallIntegerField("Опыт, лет", null=True, blank=True)
    master_bio = models.TextField("О мастере (расширенно)", blank=True)
    avatar = models.ImageField("Фото мастера (аватар)", upload_to="stations/avatars/%Y/%m/", blank=True)
    avatar_thumb = ImageSpecField(
        source="avatar",
        processors=[ResizeToFill(320, 320)],
        format="JPEG",
        options={"quality": 85},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    objects = ServiceStationManager()

    class Meta:
        verbose_name = "СТО"
        verbose_name_plural = "СТО"
        indexes = [
            models.Index(fields=["is_active", "subscription_plan"]),
            models.Index(fields=["executor_kind", "is_verified"]),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if (
            getattr(settings, "GEOCODING_ENABLED", False)
            and (self.address or "").strip()
            and self.location is None
        ):
            from .geocoding import geocode_address_to_point

            pt = geocode_address_to_point(self.address)
            if pt is not None:
                self.location = pt
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:200] or "sto"
        slug = base
        n = 0
        qs = ServiceStation.objects.exclude(pk=self.pk) if self.pk else ServiceStation.objects.all()
        while qs.filter(slug=slug).exists():
            n += 1
            suffix = f"-{n}"
            slug = f"{base[: 200 - len(suffix)]}{suffix}"
        return slug

    def is_visible_in_catalog(self, today) -> bool:
        return station_is_visible(self, today)


class WorkBay(models.Model):
    station = models.ForeignKey(
        ServiceStation,
        on_delete=models.CASCADE,
        related_name="bays",
        verbose_name="СТО",
    )
    name = models.CharField("Пост / бокс", max_length=50)

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["name", "pk"]

    def __str__(self) -> str:
        return f"{self.station.name} — {self.name}"


class StationPhoto(models.Model):
    station = models.ForeignKey(
        ServiceStation,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="СТО",
    )
    image = models.ImageField("Фото", upload_to="stations/%Y/%m/")
    image_thumb = ImageSpecField(
        source="image",
        processors=[ResizeToFill(1200, 675)],
        format="JPEG",
        options={"quality": 82},
    )
    is_work_sample = models.BooleanField("Пример работы (до/после)", default=False)
    caption = models.CharField("Подпись", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фото СТО"
        verbose_name_plural = "Фото СТО"
        ordering = ["order", "pk"]

    def clean(self):
        super().clean()
        if self.station_id:
            qs = StationPhoto.objects.filter(station_id=self.station_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= 5:
                raise ValidationError("На одну станцию можно загрузить не более 5 фотографий.")

    def __str__(self) -> str:
        return f"Фото #{self.order} ({self.station.name})"


class District(models.Model):
    """Справочник районов / зон (для фильтра «Район»)."""

    name = models.CharField("Название", max_length=120)
    slug = models.SlugField("Слаг", max_length=140, unique=True)
    city_label = models.CharField(
        "Город / регион",
        max_length=120,
        blank=True,
        help_text="Подпись в интерфейсе, например «Владикавказ».",
    )

    class Meta:
        verbose_name = "Район"
        verbose_name_plural = "Районы"
        ordering = ["city_label", "name"]

    def __str__(self) -> str:
        return self.name


class ServiceSection(models.Model):
    """Раздел услуг (группа) для UI-кнопок и фильтра каталога."""

    name = models.CharField("Раздел", max_length=120, unique=True)
    slug = models.SlugField("Слаг", max_length=140, unique=True, db_index=True)
    icon = models.CharField(
        "Иконка (Bootstrap Icons)",
        max_length=60,
        blank=True,
        help_text="Например bi-tools, bi-wrench, bi-brakes. Используется на главной.",
    )
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0, db_index=True)
    landing_lead = models.TextField(
        "Лид-текст для лендинга /razdely/",
        blank=True,
        help_text="Уникальный абзац для SEO (plain text). Пусто — только общий шаблон.",
    )
    landing_faq = models.JSONField(
        "FAQ для лендинга (JSON)",
        default=list,
        blank=True,
        help_text='Список объектов {"q": "вопрос", "a": "ответ"} для блока FAQ и разметки FAQPage.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Раздел услуг"
        verbose_name_plural = "Разделы услуг"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ServiceCategory(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    slug = models.SlugField("Слаг", max_length=140, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    section = models.ForeignKey(
        ServiceSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categories",
        verbose_name="Раздел",
        help_text="Группа услуг для кнопок/фильтра по разделу. Можно оставить пустым для точечных категорий.",
    )
    landing_lead = models.TextField(
        "Лид-текст для лендинга /uslugi/",
        blank=True,
        help_text="Уникальный абзац для SEO (plain text). Пусто — только общий шаблон.",
    )
    landing_faq = models.JSONField(
        "FAQ для лендинга (JSON)",
        default=list,
        blank=True,
        help_text='Список объектов {"q": "вопрос", "a": "ответ"} для блока FAQ и разметки FAQPage.',
    )

    class Meta:
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ServiceSearchPhrase(models.Model):
    """
    «Живая» фраза водителя → категория услуг в каталоге (для умных подсказок).
    Наполняется из словаря и админки.
    """

    phrase = models.CharField("Фраза", max_length=500)
    phrase_normalized = models.CharField("Нормализованная фраза", max_length=500, db_index=True)
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="search_phrases",
        verbose_name="Категория услуг",
    )
    weight = models.PositiveSmallIntegerField(
        "Вес (1–10)",
        default=5,
        help_text="Выше — важнее при совпадении с запросом.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Поисковая фраза"
        verbose_name_plural = "Поисковые фразы"
        constraints = [
            models.UniqueConstraint(
                fields=["phrase_normalized", "category"],
                name="stations_searchphrase_norm_cat_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["phrase_normalized", "weight"]),
        ]

    def __str__(self) -> str:
        return f"{self.phrase} → {self.category.name}"

    def save(self, *args, **kwargs):
        from .search_text import normalize_search_text

        self.phrase_normalized = normalize_search_text(self.phrase)
        super().save(*args, **kwargs)


class CarBrand(models.Model):
    name = models.CharField("Марка", max_length=60, unique=True)
    slug = models.SlugField("Слаг", max_length=80, unique=True, db_index=True)
    sprite_key = models.CharField(
        "Ключ логотипа (SVG sprite)",
        max_length=60,
        blank=True,
        help_text="ID в static/pm-brand-sprite.svg и имя static/logo/{ключ}.png (например bmw, mercedes; для VW в PNG — volkswagen).",
    )
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0, db_index=True)
    is_popular = models.BooleanField("Популярная (для главной)", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Марка авто"
        verbose_name_plural = "Марки авто"
        ordering = ["-is_popular", "sort_order", "name"]

    @property
    def logo_png_stem(self) -> str:
        """Имя файла без расширения для static/logo/{stem}.png (Volkswagen → volkswagen, не vw)."""
        slug = (self.slug or "").strip()
        sk = (self.sprite_key or "").strip()
        if slug == "volkswagen":
            return "volkswagen"
        if sk:
            return sk
        return slug

    def __str__(self) -> str:
        return self.name


class StationServiceOffer(models.Model):
    """Ориентир цены «от N ₽» по категории услуги (для карточки каталога)."""

    station = models.ForeignKey(
        ServiceStation,
        on_delete=models.CASCADE,
        related_name="service_offers",
        verbose_name="СТО",
    )
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="station_offers",
        verbose_name="Услуга",
    )
    service_title = models.CharField(
        "Название строки прайса",
        max_length=200,
        blank=True,
        help_text="Если пусто — берётся название категории.",
    )
    price_from_rub = models.PositiveIntegerField("Цена от, ₽")
    note = models.CharField("Примечание", max_length=300, blank=True)

    class Meta:
        verbose_name = "Ценовое предложение"
        verbose_name_plural = "Ценовые предложения"
        constraints = [
            models.UniqueConstraint(
                fields=["station", "category"],
                name="stations_stationoffer_station_category_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.station.name} — {self.category.name} от {self.price_from_rub} ₽"


class Promotion(models.Model):
    """Акция для главной и маркетинга (привязка к СТО опциональна)."""

    station = models.ForeignKey(
        ServiceStation,
        on_delete=models.CASCADE,
        related_name="promotions",
        verbose_name="СТО",
        null=True,
        blank=True,
        help_text="Пусто — общая акция платформы (ссылка на каталог или link_url).",
    )
    title = models.CharField("Заголовок", max_length=200)
    summary = models.TextField("Кратко", blank=True)
    link_url = models.URLField(
        "Внешняя ссылка",
        blank=True,
        help_text="Если задана, кнопка ведёт сюда; иначе — на карточку СТО (если выбрана).",
    )
    discount_percent = models.PositiveSmallIntegerField("Скидка, %", null=True, blank=True)
    valid_until = models.DateField("Действует до", null=True, blank=True)
    is_active = models.BooleanField("Активна", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return self.title
