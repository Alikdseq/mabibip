from datetime import date

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .constants import SUBSCRIPTION_PLAN_BASIC, SUBSCRIPTION_PLAN_FREE


class ServiceStationQuerySet(models.QuerySet):
    def visible_in_catalog(self, today: date | None = None):
        qs = self.filter(is_active=True, billing_blocked_at__isnull=True)
        if getattr(settings, "CATALOG_BYPASS_SUBSCRIPTION", False):
            return qs
        d = today if today is not None else timezone.now().date()
        return qs.filter(
            Q(subscription_plan=SUBSCRIPTION_PLAN_FREE)
            | Q(
                subscription_plan=SUBSCRIPTION_PLAN_BASIC,
                subscription_paid_until__gte=d,
            )
        )


class ServiceStationManager(models.Manager):
    def get_queryset(self):
        return ServiceStationQuerySet(self.model, using=self._db)

    def visible_in_catalog(self, today: date | None = None):
        return self.get_queryset().visible_in_catalog(today=today)
