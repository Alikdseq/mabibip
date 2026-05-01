from django.contrib import admin, messages

from .models import (
    Ad,
    AdCallClickEvent,
    AdCallProxy,
    AdPhoto,
    AutoShopProfile,
    AdReport,
    ImageHash,
    PhoneChangeLog,
    PhoneRevealLog,
    PartCategory,
    SellerReview,
    SellerReviewModerationStatus,
)


class AdPhotoInline(admin.TabularInline):
    model = AdPhoto
    extra = 0


@admin.register(PartCategory)
class PartCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    list_editable = ("sort_order",)
    search_fields = ("name", "slug")


@admin.register(AutoShopProfile)
class AutoShopProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "city_label", "address", "owner")
    search_fields = ("name", "slug", "city_label", "address", "owner__phone", "owner__email")


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "title",
        "price",
        "city_label",
        "is_published",
        "moderation_status",
        "view_count",
        "owner",
        "shop",
        "created_at",
    )
    list_filter = (
        "kind",
        "is_published",
        "moderation_status",
        "city_label",
        "car_transmission",
        "car_fuel",
        "car_drive",
        "car_body_type",
    )
    search_fields = (
        "title",
        "description",
        "car_model",
        "car_generation",
        "car_vin",
        "car_color",
        "owner__phone",
        "shop__name",
    )
    readonly_fields = ("view_count",)
    inlines = [AdPhotoInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "owner",
                    "shop",
                    "kind",
                    "title",
                    "price",
                    "city_label",
                    "description",
                    "is_published",
                    "moderation_status",
                    "moderation_reason",
                    "view_count",
                )
            },
        ),
        (
            "Запчасть",
            {
                "fields": ("part_category", "part_brand", "condition"),
                "classes": ("collapse",),
            },
        ),
        (
            "Автомобиль",
            {
                "fields": (
                    "car_brand",
                    "car_model",
                    "car_year",
                    "car_mileage_km",
                    "car_generation",
                    "car_engine_l",
                    "car_power_hp",
                    "car_transmission",
                    "car_fuel",
                    "car_drive",
                    "car_body_type",
                    "car_color",
                    "car_steering",
                    "car_vin",
                    "car_owners_count",
                    "car_not_crashed",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "author", "rating", "moderation_status", "created_at")
    list_filter = ("moderation_status", "rating", "created_at")
    search_fields = ("seller__phone", "author__phone", "text", "moderation_reason")
    readonly_fields = ("created_at",)
    raw_id_fields = ("seller", "author")
    ordering = ("-created_at", "-pk")
    date_hierarchy = "created_at"
    actions = ("seller_review_mark_ok", "seller_review_mark_hidden")
    fieldsets = (
        (None, {"fields": ("author", "seller", "rating", "text")}),
        (
            "Модерация",
            {"fields": ("moderation_status", "moderation_reason", "created_at")},
        ),
    )

    @admin.action(description="Статус: OK (показывать на сайте)")
    def seller_review_mark_ok(self, request, queryset):
        n = queryset.update(
            moderation_status=SellerReviewModerationStatus.OK,
            moderation_reason="",
        )
        self.message_user(request, f"Обновлено отзывов: {n}.", level=messages.SUCCESS)

    @admin.action(description="Скрыть (стандартная причина)")
    def seller_review_mark_hidden(self, request, queryset):
        n = queryset.update(
            moderation_status=SellerReviewModerationStatus.HIDDEN,
            moderation_reason="Скрыто модератором",
        )
        self.message_user(request, f"Скрыто отзывов: {n}.", level=messages.WARNING)


@admin.register(AdCallProxy)
class AdCallProxyAdmin(admin.ModelAdmin):
    list_display = ("ad", "extension", "created_at")
    search_fields = ("extension", "ad__title", "ad__pk")


@admin.register(AdCallClickEvent)
class AdCallClickEventAdmin(admin.ModelAdmin):
    list_display = ("id", "ad", "ad_kind", "user", "created_at")
    list_filter = ("ad_kind", "created_at")
    search_fields = ("ad__title", "user__phone", "user__email")
    readonly_fields = ("ad", "ad_kind", "user", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PhoneRevealLog)
class PhoneRevealLogAdmin(admin.ModelAdmin):
    list_display = ("revealed_at", "user", "ad")
    list_filter = ("revealed_at",)
    search_fields = ("user__phone", "user__email", "ad__title")
    raw_id_fields = ("user", "ad")
    date_hierarchy = "revealed_at"
    ordering = ("-revealed_at", "-pk")


@admin.register(AdReport)
class AdReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "ad", "reported_by", "reason")
    list_filter = ("created_at",)
    search_fields = ("ad__title", "reported_by__phone", "reported_by__email", "reason")
    raw_id_fields = ("ad", "reported_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")


@admin.register(PhoneChangeLog)
class PhoneChangeLogAdmin(admin.ModelAdmin):
    list_display = ("changed_at", "user", "old_phone", "new_phone", "ip")
    list_filter = ("changed_at",)
    search_fields = ("user__phone", "user__email", "old_phone", "new_phone", "ip")
    raw_id_fields = ("user",)
    date_hierarchy = "changed_at"
    ordering = ("-changed_at", "-pk")


@admin.register(ImageHash)
class ImageHashAdmin(admin.ModelAdmin):
    list_display = ("created_at", "photo", "phash")
    list_filter = ("created_at",)
    search_fields = ("phash", "photo__ad__title", "photo__ad__owner__phone")
    raw_id_fields = ("photo",)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")

