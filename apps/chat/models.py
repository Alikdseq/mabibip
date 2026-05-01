from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.chat.validators import validate_chat_attachment


def chat_epoch():
    return timezone.make_aware(timezone.datetime(1970, 1, 1))


def chat_attachment_upload_to(instance, filename: str) -> str:
    # /media/chat/<room_id>/<message_id>/<filename>
    room_id = instance.room_id or 0
    return f"chat/{room_id}/{filename}"


class ChatRoom(models.Model):
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="chat_room",
        verbose_name="Бронирование",
    )
    is_closed = models.BooleanField(default=False, verbose_name="Закрыта")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Закрыта в")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"

    def __str__(self) -> str:
        return f"ChatRoom booking={self.booking_id}"

    def can_post_messages(self) -> bool:
        return (
            self.booking.status
            in {BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS}
            and not self.is_closed
        )

    def close(self) -> None:
        if not self.is_closed:
            self.is_closed = True
            self.closed_at = timezone.now()
            self.save(update_fields=["is_closed", "closed_at"])


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages", verbose_name="Чат")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    text = models.TextField(blank=True, default="")
    attachment = models.FileField(
        upload_to=chat_attachment_upload_to,
        null=True,
        blank=True,
        validators=[validate_chat_attachment],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_by_client = models.BooleanField(default=False)
    read_by_owner = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.text:
            from .profanity import clean_text

            self.text = clean_text(self.text)
        if not self.text and not self.attachment:
            raise ValidationError("Сообщение должно содержать текст или вложение.")

    def __str__(self) -> str:
        return f"Message room={self.room_id} sender={self.sender_id}"


class ChatRoomLastRead(models.Model):
    """
    Точка отсчёта «прочитано» для пользователя в рамках комнаты.

    Используем как источник истины для подсчёта непрочитанных:
    сообщения от собеседника с created_at > last_read_at считаются непрочитанными.
    """

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="last_reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_last_reads")
    # migration-compat: earlier migrations reference ChatRoomLastRead.epoch
    @staticmethod
    def epoch():
        return chat_epoch()

    last_read_at = models.DateTimeField(default=chat_epoch)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Последнее прочтение чата"
        verbose_name_plural = "Последние прочтения чатов"
        constraints = [
            models.UniqueConstraint(fields=["room", "user"], name="chat_room_last_read_unique"),
        ]
        indexes = [
            models.Index(fields=["room", "user"]),
            models.Index(fields=["user", "-last_read_at"]),
        ]

    def __str__(self) -> str:
        return f"ChatRoomLastRead room={self.room_id} user={self.user_id}"


class UserToastEvent(models.Model):
    """
    Персистентные всплывающие уведомления (toast/pop-up), чтобы события не терялись
    пока пользователь оффлайн/не залогинен. Показываем после логина на любой странице.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="toast_events",
        verbose_name="Пользователь",
    )
    kind = models.CharField("Тип", max_length=64, db_index=True)
    payload = models.JSONField("Данные", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    seen_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Toast-уведомление"
        verbose_name_plural = "Toast-уведомления"
        indexes = [
            models.Index(fields=["user", "seen_at", "-created_at"]),
        ]
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"UserToastEvent user={self.user_id} kind={self.kind}"


class StationDirectThread(models.Model):
    """Переписка клиент ↔ станция/мастер (без привязки к конкретной записи)."""

    station = models.ForeignKey(
        "stations.ServiceStation",
        on_delete=models.CASCADE,
        related_name="direct_threads",
        verbose_name="Станция",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="station_direct_threads",
        verbose_name="Клиент",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    client_read_up_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Клиент просмотрел сообщения до",
        help_text="Сообщения от владельца с временем позже этого момента считаются непрочитанными для клиента.",
    )
    owner_read_up_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Владелец просмотрел сообщения до",
        help_text="Сообщения от клиента с временем позже этого момента считаются непрочитанными для бейджа.",
    )
    owner_archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Скрыто владельцем",
        help_text="Не показывать в списке чатов у СТО (сообщения удаляются вместе с потоком при удалении).",
    )

    class Meta:
        verbose_name = "Чат со станцией"
        verbose_name_plural = "Чаты со станциями"
        constraints = [
            models.UniqueConstraint(fields=["station", "client"], name="station_direct_thread_unique"),
        ]
        indexes = [
            models.Index(fields=["station", "-last_message_at"]),
            models.Index(fields=["station", "owner_archived_at"]),
        ]

    def __str__(self) -> str:
        return f"StationDirectThread station={self.station_id} client={self.client_id}"


class StationDirectMessage(models.Model):
    thread = models.ForeignKey(
        StationDirectThread,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Чат",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="station_direct_messages",
        verbose_name="Отправитель",
    )
    text = models.TextField("Текст")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение (чат со станцией)"
        verbose_name_plural = "Сообщения (чаты со станциями)"
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.text:
            from .profanity import clean_text

            self.text = clean_text(self.text)
        if not (self.text or "").strip():
            raise ValidationError("Введите текст сообщения.")

    def __str__(self) -> str:
        return f"StationDirectMessage thread={self.thread_id}"


class AdDirectThread(models.Model):
    """Переписка покупатель ↔ продавец по конкретному объявлению."""

    ad = models.ForeignKey(
        "classifieds.Ad",
        on_delete=models.CASCADE,
        related_name="direct_threads",
        verbose_name="Объявление",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ad_seller_threads",
        verbose_name="Продавец",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ad_buyer_threads",
        verbose_name="Покупатель",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    buyer_read_up_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Покупатель просмотрел сообщения до",
    )
    seller_read_up_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Продавец просмотрел сообщения до",
    )

    class Meta:
        verbose_name = "Чат по объявлению"
        verbose_name_plural = "Чаты по объявлениям"
        constraints = [
            models.UniqueConstraint(fields=["ad", "buyer"], name="ad_direct_thread_unique"),
        ]
        indexes = [
            models.Index(fields=["seller", "-last_message_at"]),
            models.Index(fields=["buyer", "-last_message_at"]),
        ]

    def __str__(self) -> str:
        return f"AdDirectThread ad={self.ad_id} buyer={self.buyer_id} seller={self.seller_id}"


class AdDirectMessage(models.Model):
    thread = models.ForeignKey(
        AdDirectThread,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Чат",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ad_direct_messages",
        verbose_name="Отправитель",
    )
    text = models.TextField("Текст")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение (чат по объявлению)"
        verbose_name_plural = "Сообщения (чаты по объявлениям)"
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if self.text:
            from .profanity import clean_text

            self.text = clean_text(self.text)
        if not (self.text or "").strip():
            raise ValidationError("Введите текст сообщения.")

    def __str__(self) -> str:
        return f"AdDirectMessage thread={self.thread_id}"

