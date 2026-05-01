from django.contrib import admin

from import_export.admin import ExportActionMixin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "event_type",
        "action",
        "actor",
        "object_type",
        "object_id",
        "object_label",
        "ip_address",
        "method",
        "request_path",
        "status_code",
    )
    list_filter = ("event_type", "action", "object_type", "method", "status_code")
    search_fields = ("event_type", "object_label", "object_type", "request_path", "payload")
    readonly_fields = (
        "actor",
        "event_type",
        "action",
        "object_type",
        "object_id",
        "object_label",
        "payload",
        "ip_address",
        "request_path",
        "method",
        "user_agent",
        "status_code",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

