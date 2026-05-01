from __future__ import annotations

import asyncio

import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay


User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79992220001",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79992220002", password="x", is_phone_verified=True)


@pytest.fixture
def booking(db, owner, client_user):
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО WS",
        slug="sto-ws",
        address="ул. WS, 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П1")
    from datetime import date as date_cls, time as time_cls

    slot = TimeSlot.objects.create(
        bay=bay,
        date=date_cls(2035, 1, 1),
        start_time=time_cls(10, 0),
        end_time=time_cls(11, 0),
        is_available=True,
    )
    return Booking.objects.create(
        client=client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+79990001122",
        description="d",
        status=BookingStatus.PENDING,
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_send_returns_temporarily_unavailable_when_rate_limit_backend_down(booking, client_user, monkeypatch):
    from config.asgi import application
    import apps.chat.consumers as consumers

    def _boom(*, user_id: int) -> bool:
        raise RuntimeError("redis down")

    monkeypatch.setattr(consumers, "allow_message_send", _boom)

    communicator = WebsocketCommunicator(application, f"/ws/chat/{booking.pk}/")
    communicator.scope["user"] = client_user
    connected, _ = await asyncio.wait_for(communicator.connect(), timeout=2)
    assert connected is True

    await communicator.send_json_to({"text": "hello"})
    msg = await asyncio.wait_for(communicator.receive_json_from(), timeout=2)
    assert msg["type"] == "error"
    assert msg["detail"] == "temporarily_unavailable"

    await communicator.disconnect()

