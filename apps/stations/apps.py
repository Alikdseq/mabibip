from django.apps import AppConfig


class StationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stations"
    verbose_name = "Станции (СТО)"

    def ready(self):
        from . import signals  # noqa: F401
