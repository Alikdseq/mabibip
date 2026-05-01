from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.reviews.models import ModerationStatus, Review
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay


User = get_user_model()


@pytest.mark.django_db
def test_f7_t1_simple_history_records_field_change():
    owner = User.objects.create_user(phone="+79997770001", password="x", is_phone_verified=True, is_sto_owner=True)
    client_user = User.objects.create_user(phone="+79997770002", password="x", is_phone_verified=True)

    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО-HIST",
        slug="sto-hist",
        address="ул. 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(bay=bay, date="2026-04-15", start_time="10:00", end_time="10:30")
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

    assert r.history.count() == 1
    r.moderation_status = ModerationStatus.UNDER_REVIEW
    r.moderation_reason = "complaint"
    r.save(update_fields=["moderation_status", "moderation_reason"])
    assert r.history.count() == 2
    latest = r.history.first()
    assert latest.moderation_status == ModerationStatus.UNDER_REVIEW


@pytest.mark.django_db
def test_f7_t2_mass_action_denied_for_non_superuser():
    staff = User.objects.create_user(
        phone="+79997770003",
        password="x",
        is_phone_verified=True,
        is_staff=True,
        is_superuser=False,
    )
    owner = User.objects.create_user(phone="+79997770004", password="x", is_phone_verified=True, is_sto_owner=True)
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО-ACT",
        slug="sto-act",
        address="ул. 2",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )

    c = Client()
    c.force_login(staff)
    url = reverse("admin:stations_servicestation_changelist")
    data = {"action": "notify_selected_stations", "_selected_action": [st.pk]}
    with patch("apps.stations.admin.notify_stations_task.delay") as mocked:
        resp = c.post(url, data, follow=True)
        assert resp.status_code == 200
        mocked.assert_not_called()

