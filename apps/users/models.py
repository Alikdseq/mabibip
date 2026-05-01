import uuid

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, email=None, **extra_fields):
        if not phone:
            raise ValueError("Телефон обязателен")
        email = self.normalize_email(email) if email else None
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, email=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_phone_verified", True)
        extra_fields.setdefault("email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")
        return self.create_user(phone, password, email=email, **extra_fields)


class User(AbstractUser):
    """
    Учётная запись: логин по телефону (E.164). Email опционален (чеки, рассылки).
    Фаза F1 — соответствие полному ТЗ.
    """

    class StoModerationStatus(models.TextChoices):
        """Премодерация регистрации владельца СТО (публичная заявка)."""

        APPROVED = "approved", "Одобрено"
        PENDING = "pending", "На модерации"
        REJECTED = "rejected", "Отклонено"

    username = None
    # E.164 fits in 16, but we also store anonymized values like "deleted_<suffix>".
    phone = models.CharField("Телефон (E.164)", max_length=32, unique=True, db_index=True)
    public_id = models.UUIDField(
        "Публичный идентификатор",
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Используется в публичных ссылках профиля (вместо числового id).",
    )
    email = models.EmailField(
        "Электронная почта",
        blank=True,
        null=True,
        unique=True,
        help_text="Необязательно; для чеков и восстановления пароля.",
    )
    email_verified = models.BooleanField(
        "Email подтверждён",
        default=False,
        db_index=True,
        help_text="True после перехода по ссылке из письма; при отсутствии email — не требуется.",
    )
    email_verification_token = models.CharField(
        "Токен подтверждения email",
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    contact_view_blocked_until = models.DateTimeField(
        "Просмотр контактов заблокирован до",
        null=True,
        blank=True,
        db_index=True,
        help_text="Автоблокировка при превышении лимитов раскрытия телефонов.",
    )
    is_suspicious = models.BooleanField(
        "Подозрительная активность",
        default=False,
        db_index=True,
        help_text="Флаг антифрода: ограничения на контакты/публикации при подозрительной активности.",
    )
    is_phone_verified = models.BooleanField("Телефон подтверждён", default=False)
    is_sto_owner = models.BooleanField("Владелец СТО", default=False)
    class BusinessRole(models.TextChoices):
        DRIVER = "driver", "Водитель"
        MASTER = "master", "Мастер"
        AUTOSERVICE = "autoservice", "Автосервис"
        AUTOSHOP = "autoshop", "Автомагазин/разборка"

    business_role = models.CharField(
        "Роль",
        max_length=20,
        choices=BusinessRole.choices,
        default=BusinessRole.DRIVER,
        db_index=True,
    )
    business_role_chosen = models.BooleanField(
        "Роль выбрана",
        default=False,
        db_index=True,
        help_text="True после явного выбора роли пользователем (для OAuth онбординга).",
    )
    contact_phone = models.CharField(
        "Телефон для связи (E.164)",
        max_length=32,
        blank=True,
        default="",
        db_index=True,
        help_text="Контактный номер для связи. Не используется как логин.",
    )
    sto_moderation_status = models.CharField(
        "Модерация заявки СТО",
        max_length=20,
        choices=StoModerationStatus.choices,
        default=StoModerationStatus.APPROVED,
        db_index=True,
        help_text=(
            "Для заявок с сайта — «На модерации» до проверки администратором; "
            "до одобрения ЛК СТО недоступен. Обычные клиенты и созданные админом владельцы — «Одобрено»."
        ),
    )
    sto_chat_auto_prune_inactive = models.BooleanField(
        "Автоудаление неактивных чатов (3 дня)",
        default=True,
        help_text="Если включено, переписки без сообщений более 3 суток удаляются автоматически.",
    )
    avatar = models.ImageField(
        "Фото профиля",
        upload_to="users/avatars/%Y/%m/",
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=("jpg", "jpeg", "png", "webp"),
                message="Допустимы только изображения JPG, PNG или WEBP.",
            ),
        ],
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self) -> str:
        return self.phone


class SavedCar(models.Model):
    """Автомобиль клиента для быстрой записи (сценарий ЛК)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_cars",
        verbose_name="Владелец",
    )
    license_plate = models.CharField("Госномер", max_length=20, db_index=True)
    brand_model = models.CharField("Марка / модель", max_length=200, blank=True, default="")
    vin = models.CharField("VIN", max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "сохранённое авто"
        verbose_name_plural = "сохранённые авто"
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "license_plate"],
                name="users_savedcar_user_plate_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.license_plate} ({self.user_id})"

    @property
    def display_line(self) -> str:
        plate = (self.license_plate or "").strip()
        bm = (self.brand_model or "").strip()
        if bm:
            return f"{plate} · {bm}".strip(" ·")
        return plate


class FavoriteStation(models.Model):
    """Избранные мастера / сервисы из каталога (сценарий ЛК)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_stations",
        verbose_name="Пользователь",
    )
    station = models.ForeignKey(
        "stations.ServiceStation",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="СТО",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "избранный мастер / сервис"
        verbose_name_plural = "избранные мастера и сервисы"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "station"],
                name="users_favoritestation_user_station_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.station_id}"


class PhoneVerificationChallenge(models.Model):
    """
    Одноразовая выдача кода по SMS. Код не хранится в открытом виде (только HMAC).
    """

    phone_e164 = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "запрос кода по телефону"
        verbose_name_plural = "запросы кодов по телефону"
        indexes = [
            models.Index(fields=["phone_e164", "-created_at"]),
        ]

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return self.locked_until > timezone.now()


class ContactPhoneChangeRequest(models.Model):
    """Заявка на смену контактного телефона (через админ-одобрение)."""

    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        APPROVED = "approved", "Одобрено"
        REJECTED = "rejected", "Отклонено"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_phone_change_requests",
        verbose_name="Пользователь",
    )
    old_phone_e164 = models.CharField("Старый контактный телефон (E.164)", max_length=32, blank=True, default="")
    new_phone_e164 = models.CharField("Новый контактный телефон (E.164)", max_length=32, db_index=True)
    reason = models.CharField("Причина смены", max_length=500, blank=True, default="")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    admin_comment = models.CharField("Комментарий администратора", max_length=500, blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_contact_phone_change_requests",
        verbose_name="Решение принял",
    )
    decided_at = models.DateTimeField("Решение принято", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "заявка на смену контактного телефона"
        verbose_name_plural = "заявки на смену контактного телефона"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="pending"),
                name="users_contact_phone_change_one_pending_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"ContactPhoneChangeRequest(user_id={self.user_id}, status={self.status}, new={self.new_phone_e164})"
