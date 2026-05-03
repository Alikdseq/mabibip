from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from allauth.socialaccount.models import SocialAccount

User = get_user_model()


@pytest.mark.django_db
@override_settings(VK_CLIENT_ID="123", VK_CLIENT_SECRET="secret", RATELIMIT_ENABLE=False)
def test_vkid_session_login_links_social_and_returns_redirect():
    User.objects.create_user(phone="+79991110001", password="x", email="vkuser@example.com")
    client = Client()

    with patch("apps.users.vkid.requests.post") as post:
        post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "user": {
                    "user_id": "555001",
                    "email": "vkuser@example.com",
                    "first_name": "Ivan",
                }
            },
        )
        r = client.post(
            reverse("users:vkid_session"),
            data=json.dumps({"access_token": "fake", "process": "login"}),
            content_type="application/json",
        )

    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert "redirect" in body
    assert SocialAccount.objects.filter(provider="vk", uid="555001").exists()


@pytest.mark.django_db
@override_settings(VK_CLIENT_ID="123", VK_CLIENT_SECRET="secret", RATELIMIT_ENABLE=False)
def test_vkid_session_login_no_email_returns_403():
    client = Client()
    with patch("apps.users.vkid.requests.post") as post:
        post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"user": {"user_id": "555002", "first_name": "No"}},
        )
        r = client.post(
            reverse("users:vkid_session"),
            data=json.dumps({"access_token": "x", "process": "login"}),
            content_type="application/json",
        )
    assert r.status_code == 403
    assert r.json().get("error") == "email_required"
