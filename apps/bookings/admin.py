from django.contrib import admin

from import_export.admin import ExportActionMixin

from .models import Booking, TimeSlot, WorkingHours


@admin.register(WorkingHours)
class WorkingHoursAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("bay", "weekday", "opens_at", "closes_at", "slot_duration_minutes")
    list_filter = ("weekday", "bay__station")
    autocomplete_fields = ("bay",)


@admin.register(TimeSlot)
class TimeSlotAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "bay", "is_available")
    list_filter = ("date", "is_available", "bay__station")
    search_fields = ("bay__name", "bay__station__name")
    autocomplete_fields = ("bay",)


@admin.register(Booking)
class BookingAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("id", "client", "station", "slot_datetime", "status", "created_at")
    list_filter = ("status", "station", ("created_at", admin.DateFieldListFilter))
    search_fields = ("car_info", "contact_phone", "client__email", "station__name")
    raw_id_fields = ("client", "station")
    autocomplete_fields = ("slot",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("slot", "station", "client")

    @admin.display(description="Слот")
    def slot_datetime(self, obj: Booking):
        if not obj.slot_id:
            return "—"
        s = obj.slot
        return f"{s.date} {s.start_time}–{s.end_time}"
