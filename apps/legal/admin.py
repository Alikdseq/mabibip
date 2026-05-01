from django.contrib import admin

from .models import LegalDocumentVersion, UserConsent


@admin.register(LegalDocumentVersion)
class LegalDocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("key", "version_label", "title", "effective_at", "content_checksum", "created_at")
    list_filter = ("key",)
    search_fields = ("title", "version_label")
    ordering = ("-effective_at",)
    readonly_fields = ("content_checksum", "created_at")


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "document_version", "accepted_at", "ip_address")
    list_filter = ("accepted_at",)
    search_fields = ("user__email",)
    raw_id_fields = ("user", "document_version")
    readonly_fields = ("accepted_at",)
