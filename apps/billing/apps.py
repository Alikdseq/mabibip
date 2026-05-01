from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
    verbose_name = "Биллинг и подписки"

    def ready(self):
        from . import tasks  # noqa: F401

