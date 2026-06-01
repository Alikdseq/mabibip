# -*- coding: utf-8 -*-
"""Создание отзывов о станции / мастере."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.bookings.models import Booking
from apps.reviews.models import Review
from apps.stations.models import ServiceStation

User = get_user_model()


class ReviewAlreadyExistsError(Exception):
    pass


def user_has_station_review(*, author: User, station: ServiceStation) -> bool:
    return Review.objects.filter(author=author, station=station).exists()


@transaction.atomic
def create_station_review(
    *,
    author: User,
    station: ServiceStation,
    rating: int,
    text: str = "",
    photo=None,
    booking: Booking | None = None,
) -> Review:
    if author.pk == station.owner_id:
        raise ValueError("Владелец не может оставить отзыв своей станции.")
    if user_has_station_review(author=author, station=station):
        raise ReviewAlreadyExistsError
    review = Review(
        author=author,
        station=station,
        booking=booking,
        rating=rating,
        text=(text or "").strip(),
    )
    if photo:
        review.photo = photo
    try:
        review.save()
    except IntegrityError as exc:
        raise ReviewAlreadyExistsError from exc
    return review
