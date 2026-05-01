from __future__ import annotations

import io

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
import asyncio

from apps.bookings.constants import BookingStatus
from apps.bookings.models import Booking, TimeSlot
from django.core.exceptions import ValidationError

from apps.chat.validators import validate_chat_attachment
from apps.stations.constants import SUBSCRIPTION_PLAN_FREE
from apps.stations.models import ServiceStation, WorkBay


User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        phone="+79991110001",
        password="x",
        is_sto_owner=True,
        is_phone_verified=True,
    )


@pytest.fixture
def client_user(db):
    return User.objects.create_user(phone="+79991110002", password="x", is_phone_verified=True)


@pytest.fixture
def booking(db, owner, client_user):
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО Chat",
        slug="sto-chat",
        address="ул. Чатовая, 1",
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
async def test_f5_t1_connect_to_foreign_room_denied(booking, owner):
    from config.asgi import application

    intruder = await sync_to_async(User.objects.create_user)(phone="+79991110003", password="x", is_phone_verified=True)
    communicator = WebsocketCommunicator(application, f"/ws/chat/{booking.pk}/")
    communicator.scope["user"] = intruder
    connected, _ = await asyncio.wait_for(communicator.connect(), timeout=2)
    assert connected is False


def test_f5_t2_exe_disguised_as_pdf_rejected():
    fake_exe = SimpleUploadedFile("doc.pdf", b"MZ" + b"\x00" * 20, content_type="application/pdf")
    with pytest.raises(ValidationError):
        validate_chat_attachment(fake_exe)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_f5_t3_flood_rate_limit_blocks(booking, client_user, settings):
    from config.asgi import application

    settings.CHAT_RATE_LIMIT_COUNT = 2
    settings.CHAT_RATE_LIMIT_WINDOW_SECONDS = 60

    communicator = WebsocketCommunicator(application, f"/ws/chat/{booking.pk}/")
    communicator.scope["user"] = client_user
    connected, _ = await asyncio.wait_for(communicator.connect(), timeout=2)
    assert connected is True

    await communicator.send_json_to({"text": "1"})
    await asyncio.wait_for(communicator.receive_json_from(), timeout=2)
    await communicator.send_json_to({"text": "2"})
    await asyncio.wait_for(communicator.receive_json_from(), timeout=2)
    await communicator.send_json_to({"text": "3"})
    msg = await asyncio.wait_for(communicator.receive_json_from(), timeout=2)
    assert msg["type"] == "error"
    assert msg["detail"] == "rate_limited"
    await communicator.disconnect()

