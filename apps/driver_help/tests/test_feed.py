"""Публичная лента «Нужна помощь»."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.driver_help.models import DriverHelpRequest, HelpRequestStatus
from apps.users.models import User


@pytest.mark.django_db
def test_help_feed_visible_to_guest():
    author = User.objects.create_user(phone="+79992220001", password="x", is_active=True)
    DriverHelpRequest.objects.create(author=author, message="Не заводится", status=HelpRequestStatus.ACTIVE)
    r = Client().get(reverse("driver_help:feed"))
    assert r.status_code == 200
    assert "Не заводится" in r.content.decode()


@pytest.mark.django_db
def test_help_create_requires_login():
    r = Client().post(
        reverse("driver_help:create"),
        data={"message": "Нужна помощь"},
    )
    assert r.status_code == 302
    assert "/login/" in r.url
