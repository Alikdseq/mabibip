from django.contrib import admin, messages
from django.utils.html import format_html

from import_export.admin import ExportActionMixin

from apps.audit.utils import audit_log
from apps.chat.models import Message

from .models import ModerationStatus, Review, ReviewComplaint, ReviewReply


class ReviewReplyInline(admin.StackedInline):
    model = ReviewReply
    extra = 0
    max_num = 1


class ReviewComplaintInline(admin.TabularInline):
    model = ReviewComplaint
    extra = 0
    readonly_fields = ("created_at", "resolved_at")


@admin.register(Review)
class ReviewAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "station_name",
        "rating",
        "author_phone",
        "created_at",
        "moderation_status",
    )
    autocomplete_fields = ("booking",)
    list_filter = ("moderation_status", "rating", "created_at")
    search_fields = ("booking__station__name", "booking__client__phone", "text")
    actions = ("hide_reviews",)
    inlines = [ReviewReplyInline, ReviewComplaintInline]
    readonly_fields = ("last_chat_messages", "photo_preview")
    fieldsets = (
        (None, {"fields": ("booking", "rating", "text", "photo", "photo_preview")}),
        ("Модерация", {"fields": ("moderation_status", "moderation_reason")}),
        ("Чат (последние сообщения, read-only)", {"fields": ("last_chat_messages",)}),
    )

    @admin.display(description="Превью фото")
    def photo_preview(self, obj: Review) -> str:
        if obj is None or not getattr(obj, "pk", None) or not getattr(obj, "photo", None):
            return "—"
        try:
            thumb = obj.photo_thumb.url
        except Exception:
            thumb = obj.photo.url
        return format_html(
            '<a href="{}" target="_blank" rel="noopener"><img src="{}" style="max-height:160px;border-radius:4px" alt=""/></a>',
            obj.photo.url,
            thumb,
        )

    @admin.display(description="СТО")
    def station_name(self, obj: Review) -> str:
        return obj.booking.station.name if obj.booking_id else "—"

    @admin.display(description="Автор")
    def author_phone(self, obj: Review) -> str:
        return obj.booking.client.phone if obj.booking_id else "—"

    @admin.action(description="Скрыть отзывы (модерация)")
    def hide_reviews(self, request, queryset):
        n = queryset.update(
            moderation_status=ModerationStatus.HIDDEN, moderation_reason="Скрыто администратором"
        )
        audit_log(
            request=request,
            event_type="reviews.hide_bulk",
            action="hide",
            object_label=f"Review count={n}",
            payload={},
        )
        self.message_user(
            request,
            f"Скрыто отзывов: {n}. Укажите причину в карточке при необходимости.",
            level=messages.WARNING,
        )

    def last_chat_messages(self, obj: Review) -> str:
        if obj is None or not getattr(obj, "pk", None):
            return "—"
        try:
            room = obj.booking.chat_room
        except Exception:
            return "Чат не найден."
        qs = Message.objects.filter(room=room).select_related("sender").order_by("-created_at")[:20]
        if not qs:
            return "Сообщений нет."
        lines = []
        for m in reversed(list(qs)):
            sender = getattr(m.sender, "phone", str(m.sender_id))
            txt = (m.text or "").replace("\n", " ")
            lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {sender}: {txt}")
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", "\n".join(lines))

    last_chat_messages.short_description = "Последние сообщения"


@admin.register(ReviewComplaint)
class ReviewComplaintAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("id", "review", "station", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reason", "review__booking__station__name")
    autocomplete_fields = ("review", "station")
