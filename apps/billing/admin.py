from django.contrib import admin

from import_export.admin import ExportActionMixin

from .models import PaymentIntent, PaymentProviderCustomer, ProviderWebhookEvent, Subscription


@admin.register(PaymentProviderCustomer)
class PaymentProviderCustomerAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("provider", "user", "provider_customer_id", "created_at")
    list_filter = ("provider",)
    search_fields = ("provider_customer_id", "user__phone", "user__email")
    autocomplete_fields = ("user",)


@admin.register(Subscription)
class SubscriptionAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("provider", "station", "status", "current_period_end", "next_charge_at", "failed_attempts")
    list_filter = ("provider", "status")
    search_fields = ("station__name", "station__slug")
    autocomplete_fields = ("station", "customer")


@admin.register(PaymentIntent)
class PaymentIntentAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("provider", "subscription", "status", "amount", "currency", "created_at")
    list_filter = ("provider", "status", "currency")
    search_fields = ("idempotency_key", "provider_payment_id")
    autocomplete_fields = ("subscription",)


@admin.register(ProviderWebhookEvent)
class ProviderWebhookEventAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ("provider", "provider_event_id", "received_at")
    list_filter = ("provider",)
    search_fields = ("provider_event_id",)

