from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def _user_capture_old_phone(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_phone_for_antifraud = ""
        return
    try:
        old = sender.objects.only("phone").get(pk=instance.pk)
        instance._old_phone_for_antifraud = getattr(old, "phone", "") or ""
    except Exception:
        instance._old_phone_for_antifraud = ""


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _user_log_phone_change(sender, instance, created: bool, **kwargs):
    if created:
        return
    old_phone = (getattr(instance, "_old_phone_for_antifraud", "") or "").strip()
    new_phone = (getattr(instance, "phone", "") or "").strip()
    if not old_phone or old_phone == new_phone:
        return
    if old_phone.startswith("deleted_") or new_phone.startswith("deleted_"):
        return

    def _on_commit():
        from apps.classifieds.models import PhoneChangeLog  # local import to avoid app init cycles

        PhoneChangeLog.objects.create(
            user=instance,
            old_phone=old_phone,
            new_phone=new_phone,
            ip=None,
        )

        since = timezone.now() - timedelta(hours=24)
        changes_24h = PhoneChangeLog.objects.filter(user=instance, changed_at__gte=since).count()
        if changes_24h > 2:
            sender.objects.filter(pk=instance.pk, is_suspicious=False).update(is_suspicious=True)

    transaction.on_commit(_on_commit)

