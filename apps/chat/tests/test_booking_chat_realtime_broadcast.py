"""Регрессии: мгновенная доставка сообщений в чате по записи (group_send + корректный type на клиенте)."""

from __future__ import annotations

import asyncio

import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay

User = get_user_model()

_IN_MEMORY_CHANNELS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@pytest.fixture
def chat_owner(db):
    return User.objects.create_user(
        phone="+79993330001",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def chat_client_user(db):
    return User.objects.create_user(phone="+79993330002", password="x", is_phone_verified=True)


@pytest.fixture
def chat_booking(db, chat_owner, chat_client_user):
    st = ServiceStation.objects.create(
        owner=chat_owner,
        name="СТО Realtime",
        slug="sto-rt",
        address="ул. RT, 1",
        subscription_plan=SUBSCRIPTION_PLAN_FREE,
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П1")
    from datetime import date as date_cls, time as time_cls

    slot = TimeSlot.objects.create(
        bay=bay,
        date=date_cls(2035, 2, 1),
        start_time=time_cls(10, 0),
        end_time=time_cls(11, 0),
        is_available=True,
    )
    return Booking.objects.create(
        client=chat_client_user,
        station=st,
        slot=slot,
        car_info="A",
        contact_phone="+79990003322",
        description="d",
        status=BookingStatus.PENDING,
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=_IN_MEMORY_CHANNELS)
async def test_booking_chat_broadcasts_type_message_to_both_participants(chat_booking, chat_owner, chat_client_user):
    from config.asgi import application

    path = f"/ws/chat/{chat_booking.pk}/"
    comm_a = WebsocketCommunicator(application, path)
    comm_a.scope["user"] = chat_client_user
    comm_b = WebsocketCommunicator(application, path)
    comm_b.scope["user"] = chat_owner

    connected_a, _ = await asyncio.wait_for(comm_a.connect(), timeout=3)
    connected_b, _ = await asyncio.wait_for(comm_b.connect(), timeout=3)
    assert connected_a is True
    assert connected_b is True

    await comm_a.send_json_to({"text": "мгновенная доставка"})

    raw_a, raw_b = await asyncio.gather(
        asyncio.wait_for(comm_a.receive_json_from(), timeout=3),
        asyncio.wait_for(comm_b.receive_json_from(), timeout=3),
    )

    for msg in (raw_a, raw_b):
        assert msg["type"] == "message", msg
        assert msg["text"] == "мгновенная доставка"
        assert int(msg["sender_id"]) == chat_client_user.pk
        assert "id" in msg and msg["id"]
        assert "created_at" in msg

    await comm_a.disconnect()
    await comm_b.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=_IN_MEMORY_CHANNELS)
async def test_booking_chat_ping_pong(chat_booking, chat_client_user):
    from config.asgi import application

    comm = WebsocketCommunicator(application, f"/ws/chat/{chat_booking.pk}/")
    comm.scope["user"] = chat_client_user
    connected, _ = await asyncio.wait_for(comm.connect(), timeout=3)
    assert connected is True

    await comm.send_json_to({"type": "ping", "t": 42})
    msg = await asyncio.wait_for(comm.receive_json_from(), timeout=3)
    assert msg == {"type": "pong", "t": 42}

    await comm.disconnect()
