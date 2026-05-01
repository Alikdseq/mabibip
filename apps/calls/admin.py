from django.contrib import admin

from .models import Call


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "caller",
        "receiver",
        "context_kind",
        "context_id",
        "ad",
        "started_at",
        "ended_at",
        "room_name",
    )
    list_filter = ("status", "context_kind", "created_at")
    search_fields = ("room_name", "caller__phone", "receiver__phone", "caller__email", "receiver__email")
    raw_id_fields = ("caller", "receiver", "ad")
    readonly_fields = ("created_at", "updated_at")

