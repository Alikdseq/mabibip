from django.contrib import admin

from .models import SupportMessage, SupportTicket


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("created_at", "author", "is_staff_reply", "is_system_auto")
    ordering = ("created_at", "pk")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "subject", "created_at", "updated_at", "user_last_read_at", "staff_last_read_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "user__phone", "user__email")
    readonly_fields = ("created_at", "updated_at", "user_last_read_at", "staff_last_read_at")
    raw_id_fields = ("user",)
    inlines = [SupportMessageInline]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "author", "is_staff_reply", "is_system_auto", "created_at")
    list_filter = ("is_staff_reply", "is_system_auto", "created_at")
    search_fields = ("body", "ticket__user__phone")
    readonly_fields = ("created_at",)
    raw_id_fields = ("ticket", "author")
