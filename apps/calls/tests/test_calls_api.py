from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.calls.models import Call, CallStatus


@pytest.mark.django_db
@override_settings(CALLS_ENABLED=True, LIVEKIT_URL="https://lk.example", LIVEKIT_API_KEY="k", LIVEKIT_API_SECRET="s")
def test_calls_initiate_and_decline(monkeypatch):
    # avoid real token generation/deps
    monkeypatch.setattr("apps.calls.api_views.issue_room_token", lambda **kw: "tok")

    User = get_user_model()
    caller = User.objects.create_user(
        phone="+79990000001",
        password="x",
        is_active=True,
        contact_phone="+79990000001",
    )
    receiver = User.objects.create_user(
        phone="+79990000002",
        password="x",
        is_active=True,
        contact_phone="+79990000002",
    )

    c = APIClient()
    c.force_authenticate(user=caller)
    r = c.post("/api/calls/initiate/", {"receiver_user_id": receiver.pk}, format="json")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    call_id = int(data["call_id"])
    call = Call.objects.get(pk=call_id)
    assert call.status == CallStatus.RINGING

    c2 = APIClient()
    c2.force_authenticate(user=receiver)
    r2 = c2.post("/api/calls/action/", {"call_id": call_id, "action": "decline"}, format="json")
    assert r2.status_code == 200
    call.refresh_from_db()
    assert call.status == CallStatus.DECLINED


@pytest.mark.django_db
@override_settings(CALLS_ENABLED=True, LIVEKIT_URL="https://lk.example", LIVEKIT_API_KEY="k", LIVEKIT_API_SECRET="s")
def test_calls_accept_requires_receiver(monkeypatch):
    monkeypatch.setattr("apps.calls.api_views.issue_room_token", lambda **kw: "tok")

    User = get_user_model()
    caller = User.objects.create_user(
        phone="+79990000011",
        password="x",
        is_active=True,
        contact_phone="+79990000011",
    )
    receiver = User.objects.create_user(
        phone="+79990000012",
        password="x",
        is_active=True,
        contact_phone="+79990000012",
    )

    c = APIClient()
    c.force_authenticate(user=caller)
    r = c.post("/api/calls/initiate/", {"receiver_user_id": receiver.pk}, format="json")
    call_id = int(r.json()["call_id"])

    # caller cannot accept
    r2 = c.post("/api/calls/action/", {"call_id": call_id, "action": "accept"}, format="json")
    assert r2.status_code == 403

    c2 = APIClient()
    c2.force_authenticate(user=receiver)
    r3 = c2.post("/api/calls/action/", {"call_id": call_id, "action": "accept"}, format="json")
    assert r3.status_code == 200
    call = Call.objects.get(pk=call_id)
    assert call.status == CallStatus.ACTIVE

    # end is idempotent for both sides
    r4 = c.post("/api/calls/action/", {"call_id": call_id, "action": "end"}, format="json")
    assert r4.status_code == 200
    call.refresh_from_db()
    assert call.status in (CallStatus.COMPLETED, CallStatus.MISSED)

