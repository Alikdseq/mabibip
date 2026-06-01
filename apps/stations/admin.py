from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.db.models import Avg, Q
from django.utils import timezone

from import_export.admin import ExportActionMixin

from apps.audit.utils import audit_log
from apps.bookings.constants import BookingStatus
from apps.reviews.models import ModerationStatus

from .models import (
    CarBrand,
    District,
    Promotion,
    ServiceSection,
    ServiceCategory,
    ServiceSearchPhrase,
    ServiceStation,
    StationPhoto,
    StationServiceOffer,
    WorkBay,
)
from .tasks import notify_stations_task


@admin.register(ServiceSection)
class ServiceSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    list_editable = ("sort_order",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class WorkBayInline(admin.TabularInline):
    model = WorkBay
    extra = 0


class StationPhotoInline(admin.TabularInline):
    model = StationPhoto
    extra = 0
    max_num = 5
    fields = ("image", "order", "is_work_sample", "caption")


class StationServiceOfferInline(admin.TabularInline):
    model = StationServiceOffer
    extra = 0
    autocomplete_fields = ("category",)
    fields = ("category", "service_title", "price_from_rub", "note")


@admin.register(ServiceStation)
class ServiceStationAdmin(ExportActionMixin, gis_admin.GISModelAdmin):
    list_display = (
        "name",
        "executor_kind",
        "owner",
        "subscription_plan",
        "subscription_paid_until",
        "is_verified",
        "avg_rating_display",
        "is_active",
        "created_at",
    )
    list_filter = (
        "subscription_plan",
        "is_active",
        "executor_kind",
        "is_verified",
        "is_open_24_7",
        "district",
        ("subscription_paid_until", admin.DateFieldListFilter),
    )
    search_fields = ("name", "address", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("owner", "district")
    inlines = [WorkBayInline, StationPhotoInline, StationServiceOfferInline]
    actions = [
        "notify_selected_stations",
        "extend_subscription_30_days",
        "deactivate_selected_stations",
    ]
    filter_horizontal = ("service_sections", "categories", "car_brands")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "owner",
                    "address",
                    "address_public_mode",
                    "location",
                    "description",
                ),
            },
        ),
        (
            "Публичная карточка (тексты)",
            {
                "fields": (
                    "description_short",
                    "work_schedule_text",
                    "tagline",
                    "experience_years",
                    "master_bio",
                    "avatar",
                ),
            },
        ),
        (
            "Контакты и соцсети",
            {
                "fields": (
                    "contact_phone",
                    "whatsapp_phone",
                    "telegram_username",
                    "website",
                    "vk_url",
                    "instagram_url",
                ),
            },
        ),
        (
            "Каталог и монетизация",
            {
                "fields": (
                    "subscription_plan",
                    "subscription_paid_until",
                    "is_active",
                    "service_sections",
                    "categories",
                    "car_brands",
                )
            },
        ),
        (
            "Карточка в каталоге (фильтры)",
            {
                "fields": (
                    "executor_kind",
                    "is_verified",
                    "is_open_24_7",
                    "district",
                    "amenity_wifi",
                    "amenity_coffee",
                    "amenity_cards",
                    "amenity_tow",
                    "amenity_legal",
                    "has_parking",
                    "certified_partner",
                    "license_held",
                ),
            },
        ),
        (
            "Юр. данные (для клиентов на сайте)",
            {"fields": ("inn", "ogrn")},
        ),
    )

    def has_view_permission(self, request, obj=None):
        # MVP: staff may view; destructive actions restricted separately.
        if request.user and request.user.is_active and request.user.is_staff:
            return True
        return super().has_view_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        # Staff may open changelist/pages; per-model permissions out of MVP scope.
        if request.user and request.user.is_active and request.user.is_staff:
            return True
        return super().has_change_permission(request, obj=obj)

    @admin.display(description="Рейтинг")
    def avg_rating_display(self, obj: ServiceStation):
        v = getattr(obj, "station_avg_rating", None)
        return f"{float(v):.1f}" if v is not None else "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        rev_station = Q(reviews__moderation_status__in=["ok", "under_review"])
        return qs.annotate(station_avg_rating=Avg("reviews__rating", filter=rev_station))

    @admin.action(
        description="Продлить подписку (оплачено до) на 30 дней от max(сегодня, текущая дата)"
    )
    def extend_subscription_30_days(self, request, queryset):
        today = timezone.localdate()
        updated = 0
        for st in queryset:
            base = (
                st.subscription_paid_until
                if st.subscription_paid_until and st.subscription_paid_until > today
                else today
            )
            st.subscription_paid_until = base + timedelta(days=30)
            st.save(update_fields=["subscription_paid_until"])
            updated += 1
        audit_log(
            request=request,
            event_type="stations.subscription_extend_30",
            action="extend_subscription",
            object_label=f"ServiceStation count={updated}",
            payload={"ids": list(queryset.values_list("id", flat=True))[:50]},
        )
        self.message_user(request, f"Дата «оплачено до» обновлена у {updated} СТО.")

    @admin.action(description="Снять с публикации (is_active=False)")
    def deactivate_selected_stations(self, request, queryset):
        ids = list(queryset.values_list("id", flat=True))
        queryset.update(is_active=False)
        audit_log(
            request=request,
            event_type="stations.deactivate_bulk",
            action="deactivate",
            object_label=f"ServiceStation ids={ids[:30]}{'…' if len(ids) > 30 else ''}",
            payload={"count": len(ids)},
        )
        self.message_user(request, f"Деактивировано СТО: {len(ids)}.")

    @admin.action(description="Рассылка уведомления выбранным СТО (Celery)")
    def notify_selected_stations(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Недостаточно прав: рассылка доступна только суперпользователю.",
                level=messages.ERROR,
            )
            return

        station_ids = list(queryset.values_list("id", flat=True))
        if not station_ids:
            return

        notify_stations_task.delay(station_ids)

        tail = "…" if len(station_ids) > 20 else ""
        label = f"ServiceStation ids={station_ids[:20]}{tail}"
        audit_log(
            request=request,
            event_type="stations.mass_notify",
            action="notify",
            object_label=label,
            payload={"station_ids": station_ids, "queued_at": timezone.now().isoformat()},
        )
        self.message_user(
            request,
            f"Задача рассылки поставлена в очередь для {len(station_ids)} СТО.",
        )


@admin.register(WorkBay)
class WorkBayAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("name", "station")
    list_filter = ("station",)
    search_fields = ("name", "station__name")
    autocomplete_fields = ("station",)


@admin.register(District)
class DistrictAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "city_label")
    search_fields = ("name", "slug", "city_label")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(StationServiceOffer)
class StationServiceOfferAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("station", "category", "price_from_rub")
    list_filter = ("category",)
    search_fields = ("station__name", "category__name")
    autocomplete_fields = ("station", "category")


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("id", "name", "slug", "section", "created_at")
    list_filter = ("section",)
    search_fields = ("name", "slug", "section__name")
    autocomplete_fields = ("section",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "section")}),
        (
            "SEO: лендинг /uslugi/",
            {
                "fields": ("landing_lead", "landing_faq"),
                "description": "FAQ — JSON-массив вида [{\"q\": \"...\", \"a\": \"...\"}, ...]",
            },
        ),
    )


@admin.register(ServiceSearchPhrase)
class ServiceSearchPhraseAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("phrase", "category", "weight", "phrase_normalized", "created_at")
    list_filter = ("category",)
    search_fields = ("phrase", "phrase_normalized", "category__name")
    autocomplete_fields = ("category",)
    ordering = ("category__name", "phrase")


@admin.register(CarBrand)
class CarBrandAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_popular", "sort_order", "sprite_key", "created_at")
    list_filter = ("is_popular",)
    search_fields = ("name", "slug", "sprite_key")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("-is_popular", "sort_order", "name")


@admin.register(Promotion)
class PromotionAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "station",
        "discount_percent",
        "valid_until",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("title", "summary", "station__name")
    autocomplete_fields = ("station",)
    ordering = ("sort_order", "-created_at")
