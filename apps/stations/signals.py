"""Инвалидация кэша карточки при изменениях, влияющих на публичное отображение (фаза F2)."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.stations.card_cache import invalidate_station_card
from apps.stations.models import ServiceStation, StationPhoto, WorkBay


@receiver(post_save, sender=ServiceStation)
@receiver(post_delete, sender=ServiceStation)
def bust_cache_service_station(sender, instance, **kwargs):
    invalidate_station_card(instance.pk)


@receiver(post_save, sender=StationPhoto)
@receiver(post_delete, sender=StationPhoto)
def bust_cache_station_photo(sender, instance, **kwargs):
    invalidate_station_card(instance.station_id)


@receiver(post_save, sender=WorkBay)
@receiver(post_delete, sender=WorkBay)
def bust_cache_work_bay(sender, instance, **kwargs):
    invalidate_station_card(instance.station_id)


@receiver(post_save, sender="reviews.Review")
@receiver(post_delete, sender="reviews.Review")
def bust_cache_review(sender, instance, **kwargs):
    station_id = instance.station_id or (
        instance.booking.station_id if instance.booking_id else None
    )
    if station_id:
        invalidate_station_card(station_id)


@receiver(post_save, sender="bookings.Booking")
@receiver(post_delete, sender="bookings.Booking")
def bust_cache_booking(sender, instance, **kwargs):
    invalidate_station_card(instance.station_id)
