from __future__ import annotations

from django.conf import settings


class PrimaryReplicaRouter:
    """
    F9.1.2: routing reads to a replica under feature flag.

    Ограничения:
    - По умолчанию Django не передаёт "hints" из view; поэтому для MVP роутим
      чтение выбранных app_label целиком, когда флаг включён.
    - Записи и миграции всегда идут в default.
    """

    READ_APPS = {"stations", "reviews", "bookings"}

    def _enabled(self) -> bool:
        return bool(getattr(settings, "READ_REPLICA_ENABLED", False)) and "replica" in settings.DATABASES

    def db_for_read(self, model, **hints):
        if not self._enabled():
            return None
        if model._meta.app_label in self.READ_APPS:
            return "replica"
        return None

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # replica is read-only; we never migrate it in the app layer.
        if db == "replica":
            return False
        return True

