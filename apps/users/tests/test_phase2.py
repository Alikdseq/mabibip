"""Фаза 2 + F1: пользователь, регистрация (телефон + пароль), активация (legacy), вход (телефон)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.users import views
from apps.users.tests.registration_helpers import REGISTRATION_SECURITY_POST

User = get_user_model()


@pytest.mark.django_db
def test_create_user_success():
    user = User.objects.create_user(phone="+79991112233", password="x", email="a@b.c")
    assert user.pk
    assert user.phone == "+79991112233"
    assert user.check_password("x")


@pytest.mark.django_db
def test_phone_unique_integrity_error():
    User.objects.create_user(phone="+79991112244", password="x")
    with pytest.raises(IntegrityError):
        User.objects.create_user(phone="+79991112244", password="y")


@pytest.mark.django_db
def test_register_full_flow_active_user():
    phone = "+79991112255"
    client = Client()
    client.get(reverse("users:register"))
    r2 = client.post(
        reverse("users:register"),
        data={
            "phone": phone,
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "role": "driver",
            "email": "phase2driver@example.com",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r2.status_code == 302
    assert r2["Location"] == reverse("home")
    user = User.objects.get(phone=phone)
    assert user.is_active is True
    assert user.is_phone_verified is True
    assert user.email == "phase2driver@example.com"
    assert user.email_verified is False


@pytest.mark.django_db
def test_activate_valid_token_legacy_email_user():
    user = User.objects.create_user(
        phone="+79991112266",
        password="p",
        email="act@example.com",
        is_active=False,
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    client = Client()
    url = reverse("users:activate", kwargs={"uidb64": uid, "token": token})
    r = client.get(url)
    assert r.status_code == 302
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_activate_invalid_token():
    user = User.objects.create_user(
        phone="+79991112277",
        password="p",
        email="bad@example.com",
        is_active=False,
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    client = Client()
    url = reverse("users:activate", kwargs={"uidb64": uid, "token": "invalid-token"})
    r = client.get(url)
    assert r.status_code == 302
    user.refresh_from_db()
    assert user.is_active is False


def test_register_start_view_not_csrf_exempt():
    assert getattr(views.register_start, "csrf_exempt", False) is False


@pytest.mark.django_db
def test_register_post_rejected_without_csrf():
    client = Client(enforce_csrf_checks=True)
    client.get(reverse("users:register"))
    r = client.post(
        reverse("users:register"),
        data={
            "phone": "+79991112288",
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_login_active_user_redirects():
    """H3: обычный пользователь (водитель) после входа перенаправляется на главную."""
    User.objects.create_user(
        phone="+79991112299",
        password="secret-123",
        is_active=True,
        business_role=User.BusinessRole.DRIVER,
        is_sto_owner=False,
    )
    client = Client()
    r = client.post(
        reverse("users:login"),
        data={
            "username": "+79991112299",
            "password": "secret-123",
            "recaptcha_token": "",
        },
    )
    assert r.status_code == 302
    assert r["Location"] == reverse("home")


@pytest.mark.django_db
def test_login_sto_owner_approved_redirects_to_dashboard():
    User.objects.create_user(
        phone="+79991115600",
        password="secret-123",
        is_active=True,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
    )
    client = Client()
    r = client.post(
        reverse("users:login"),
        data={
            "username": "+79991115600",
            "password": "secret-123",
            "recaptcha_token": "",
        },
    )
    assert r.status_code == 302
    assert r["Location"] == reverse("sto_owner:dashboard")


@pytest.mark.django_db
def test_login_sto_owner_pending_redirects_to_pending_page():
    User.objects.create_user(
        phone="+79991115601",
        password="secret-123",
        is_active=True,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.PENDING,
    )
    client = Client()
    r = client.post(
        reverse("users:login"),
        data={
            "username": "+79991115601",
            "password": "secret-123",
            "recaptcha_token": "",
        },
    )
    assert r.status_code == 302
    assert r["Location"] == reverse("sto_owner:pending_moderation")


@pytest.mark.django_db
def test_login_sto_owner_rejected_redirects_to_rejected_page():
    User.objects.create_user(
        phone="+79991115602",
        password="secret-123",
        is_active=True,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.REJECTED,
    )
    client = Client()
    r = client.post(
        reverse("users:login"),
        data={
            "username": "+79991115602",
            "password": "secret-123",
            "recaptcha_token": "",
        },
    )
    assert r.status_code == 302
    assert r["Location"] == reverse("sto_owner:moderation_rejected")


@pytest.mark.django_db
def test_login_sto_owner_next_param_overrides_dashboard():
    User.objects.create_user(
        phone="+79991115603",
        password="secret-123",
        is_active=True,
        is_sto_owner=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
    )
    client = Client()
    login_url = reverse("users:login") + "?next=/cabinet/bookings/"
    r = client.post(
        login_url,
        data={
            "username": "+79991115603",
            "password": "secret-123",
            "recaptcha_token": "",
            "next": "/cabinet/bookings/",
        },
    )
    assert r.status_code == 302
    assert r["Location"] == "/cabinet/bookings/"


@pytest.mark.django_db
def test_login_inactive_user_fails():
    User.objects.create_user(
        phone="+79991112300",
        password="secret-123",
        is_active=False,
    )
    client = Client()
    r = client.post(
        reverse("users:login"),
        data={
            "username": "+79991112300",
            "password": "secret-123",
            "recaptcha_token": "",
        },
    )
    assert r.status_code == 200
