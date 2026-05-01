import secrets

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count
from django.utils import timezone

from import_export.admin import ExportActionMixin

from apps.audit.utils import audit_log
from apps.stations.models import ServiceStation

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import ContactPhoneChangeRequest, FavoriteStation, PhoneVerificationChallenge, SavedCar, User


@admin.register(User)
class UserAdmin(ExportActionMixin, DjangoUserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    model = User
    list_display = (
        "phone",
        "email",
        "email_verified",
        "business_role",
        "business_role_chosen",
        "contact_phone",
        "is_suspicious",
        "is_sto_owner",
        "sto_moderation_status",
        "is_phone_verified",
        "is_staff",
        "is_active",
        "date_joined",
        "bookings_count",
        "last_login",
    )
    list_filter = (
        "is_staff",
        "is_active",
        "is_sto_owner",
        "sto_moderation_status",
        "is_phone_verified",
        "email_verified",
        "is_suspicious",
        "business_role",
        "business_role_chosen",
        "date_joined",
    )
    search_fields = ("phone", "email")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login")
    actions = (
        "deactivate_users",
        "activate_users",
        "reset_password_random_one",
        "approve_sto_moderation",
    )

    @admin.display(description="Записей (клиент)")
    def bookings_count(self, obj: User) -> int:
        return int(getattr(obj, "_bookings_count", 0) or 0)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(_bookings_count=Count("bookings", distinct=True))
        )

    @admin.action(description="Заблокировать (is_active=False)")
    def deactivate_users(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        queryset.update(is_active=False)
        audit_log(
            request=request,
            event_type="users.deactivate_bulk",
            action="deactivate",
            object_label=f"User ids={ids[:30]}{'…' if len(ids) > 30 else ''}",
            payload={"count": len(ids)},
        )
        self.message_user(request, f"Заблокировано учётных записей: {len(ids)}.")

    @admin.action(description="Разблокировать (is_active=True)")
    def activate_users(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        queryset.update(is_active=True)
        audit_log(
            request=request,
            event_type="users.activate_bulk",
            action="activate",
            object_label=f"User ids={ids[:30]}{'…' if len(ids) > 30 else ''}",
            payload={"count": len(ids)},
        )
        self.message_user(request, f"Разблокировано учётных записей: {len(ids)}.")

    @admin.action(description="Случайный пароль (только если выбран 1 пользователь)")
    def reset_password_random_one(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Выберите ровно одного пользователя для сброса пароля.",
                level=messages.ERROR,
            )
            return
        user = queryset.first()
        new_pw = secrets.token_urlsafe(12)
        user.set_password(new_pw)
        user.save(update_fields=["password"])
        audit_log(
            request=request,
            event_type="users.password_reset_admin",
            action="password_reset",
            obj=user,
            object_label=f"User id={user.pk}",
            payload={},
        )
        self.message_user(
            request,
            f"Новый пароль для {user.phone}: {new_pw} (сообщите пользователю безопасным каналом).",
            level=messages.WARNING,
        )

    @admin.action(description="Одобрить модерацию СТО и включить станции в каталоге")
    def approve_sto_moderation(self, request, queryset):
        qs = queryset.filter(is_sto_owner=True).exclude(
            sto_moderation_status=User.StoModerationStatus.APPROVED
        )
        user_ids = list(qs.values_list("pk", flat=True))
        n = 0
        for user in qs:
            user.sto_moderation_status = User.StoModerationStatus.APPROVED
            user.save(update_fields=["sto_moderation_status"])
            ServiceStation.objects.filter(owner=user).update(is_active=True)
            n += 1
        audit_log(
            request=request,
            event_type="users.sto_moderation_approve_bulk",
            action="approve",
            object_label=f"Users approved count={n}",
            payload={"user_ids": user_ids[:200]},
        )
        self.message_user(request, f"Одобрено учётных записей владельцев СТО: {n}.")

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (
            "Профиль",
            {
                "fields": (
                    "email",
                    "email_verified",
                    "email_verification_token",
                    "business_role",
                    "business_role_chosen",
                    "contact_phone",
                    "contact_view_blocked_until",
                    "is_suspicious",
                    "avatar",
                    "is_phone_verified",
                    "is_sto_owner",
                    "sto_moderation_status",
                )
            },
        ),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone", "email", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )


@admin.register(SavedCar)
class SavedCarAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("license_plate", "brand_model", "user", "updated_at")
    search_fields = ("license_plate", "brand_model", "user__phone")
    list_filter = ("updated_at",)
    raw_id_fields = ("user",)


@admin.register(FavoriteStation)
class FavoriteStationAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("user", "station", "created_at")
    search_fields = ("user__phone", "station__name", "station__slug")
    list_filter = ("created_at",)
    raw_id_fields = ("user", "station")


@admin.register(PhoneVerificationChallenge)
class PhoneVerificationChallengeAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("phone_e164", "attempts", "locked_until", "created_at", "last_ip")
    list_filter = ("created_at",)
    readonly_fields = (
        "phone_e164",
        "code_hash",
        "attempts",
        "locked_until",
        "created_at",
        "last_ip",
    )


@admin.register(ContactPhoneChangeRequest)
class ContactPhoneChangeRequestAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("created_at", "status", "user", "old_phone_e164", "new_phone_e164", "reason", "decided_at")
    list_filter = ("status", "created_at", "decided_at")
    search_fields = ("user__phone", "user__email", "old_phone_e164", "new_phone_e164", "reason")
    raw_id_fields = ("user", "decided_by")
    readonly_fields = ("created_at", "decided_at")
    actions = ("approve_requests", "reject_requests")

    @admin.action(description="Одобрить (применить новый телефон)")
    def approve_requests(self, request, queryset):
        qs = queryset.filter(status=ContactPhoneChangeRequest.Status.PENDING)
        n = 0
        for obj in qs.select_related("user"):
            u = obj.user
            new_phone = (obj.new_phone_e164 or "").strip()
            if not new_phone:
                continue
            u.contact_phone = new_phone
            u.save(update_fields=["contact_phone"])
            # синхронизация контакта автомагазина, если профиль есть
            shop = getattr(u, "autoshop_profile", None)
            if shop:
                shop.contact_phone = new_phone
                shop.save(update_fields=["contact_phone"])

            obj.status = ContactPhoneChangeRequest.Status.APPROVED
            obj.decided_by = request.user
            obj.decided_at = timezone.now()
            obj.save(update_fields=["status", "decided_by", "decided_at"])
            n += 1

        audit_log(
            request=request,
            event_type="users.contact_phone_change_approve_bulk",
            action="approve",
            object_label=f"ContactPhoneChangeRequest approved count={n}",
            payload={"ids": list(qs.values_list('pk', flat=True))[:200]},
        )
        self.message_user(request, f"Одобрено заявок: {n}.")

    @admin.action(description="Отклонить")
    def reject_requests(self, request, queryset):
        qs = queryset.filter(status=ContactPhoneChangeRequest.Status.PENDING)
        now = timezone.now()
        n = qs.update(status=ContactPhoneChangeRequest.Status.REJECTED, decided_by=request.user, decided_at=now)
        audit_log(
            request=request,
            event_type="users.contact_phone_change_reject_bulk",
            action="reject",
            object_label=f"ContactPhoneChangeRequest rejected count={n}",
            payload={"ids": list(qs.values_list('pk', flat=True))[:200]},
        )
        self.message_user(request, f"Отклонено заявок: {n}.")
