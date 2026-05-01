from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import ComplaintStatus, Review, ReviewComplaint
from apps.reviews.tasks import detect_review_anomalies
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay
from apps.users.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79994440201",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79994440202", password="x", is_phone_verified=True)


@pytest.mark.django_db
def test_f6_t1_complaint_does_not_delete_review(owner, client_user):
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО-F6",
        slug="sto-f6",
        address="ул. F6",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=timezone.now().time().replace(second=0, microsecond=0),
        end_time=timezone.now().time().replace(second=0, microsecond=0),
    )
    b = Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+7",
        description="d",
        status=BookingStatus.COMPLETED,
    )
    r = Review.objects.create(booking=b, rating=5, text="ok")
    ReviewComplaint.objects.create(review=r, station=st, reason="spam", status=ComplaintStatus.PENDING)

    assert Review.objects.filter(pk=r.pk).exists() is True


@pytest.mark.django_db
def test_f6_t2_anomaly_detection_triggers_on_synthetic_data(settings, owner):
    settings.REVIEW_ANOMALY_MIN_FIVE_STARS = 5
    settings.REVIEW_ANOMALY_NEW_USER_AGE_DAYS = 1
    settings.REVIEW_ANOMALY_STATION_AGE_DAYS = 30
    settings.REVIEW_ANOMALY_WINDOW_HOURS = 24

    now = timezone.now()

    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО-Anom",
        slug="sto-anom",
        address="ул. Anom",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    ServiceStation.objects.filter(pk=st.pk).update(created_at=now - timedelta(days=2))
    bay = WorkBay.objects.create(station=st, name="П1")

    for i in range(6):
        u = User.objects.create_user(phone=f"+79995550{i:03d}", password="x", is_phone_verified=True)
        User.objects.filter(pk=u.pk).update(date_joined=now - timedelta(hours=2))
        slot = TimeSlot.objects.create(
            bay=bay,
            date=timezone.localdate(),
            start_time=(now + timedelta(minutes=i)).time().replace(second=0, microsecond=0),
            end_time=(now + timedelta(minutes=i + 1)).time().replace(second=0, microsecond=0),
        )
        b = Booking.objects.create(
            client=u,
            station=st,
            slot=slot,
            car_info="A",
            contact_phone="+7",
            description="d",
            status=BookingStatus.COMPLETED,
        )
        Review.objects.create(booking=b, rating=5, text="great")

    ids = detect_review_anomalies()
    assert st.pk in ids

