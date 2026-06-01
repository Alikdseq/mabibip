"""Фаза F1: django-axes, удаление аккаунта; регистрация по телефону и паролю (без SMS)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.legal.models import UserConsent
from apps.users.services_anonymize import anonymize_user
from apps.users.tests.registration_helpers import DRIVER_LITE_SECURITY_POST, REGISTRATION_SECURITY_POST

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _register_post(phone: str, **extra):
    return {
        "phone": phone,
        "password1": "strong-pass-9",
        "password2": "strong-pass-9",
        "role": "driver",
        "accept_privacy": "on",
        "accept_user_agreement": "on",
        "accept_pd_consent": "on",
        "recaptcha_token": "",
        **REGISTRATION_SECURITY_POST,
        **extra,
    }


@pytest.mark.django_db
@override_settings(
    AXES_ENABLED=True,
    AUTHENTICATION_BACKENDS=[
        "axes.backends.AxesBackend",
        "django.contrib.auth.backends.ModelBackend",
    ],
)
def test_axes_records_failed_login_attempts():
    """F1.T2: axes фиксирует неудачные попытки входа (база AccessAttempt). Полный lockout на проде — см. AXES_* в settings."""
    from axes.models import AccessAttempt

    User.objects.create_user(phone="+79991117777", password="secret-ok", is_active=True)
    client = Client()
    url = reverse("users:login")
    for _ in range(5):
        client.post(
            url,
            data={
                "username": "+79991117777",
                "password": "wrong",
                "recaptcha_token": "",
            },
        )
    assert AccessAttempt.objects.exists()
    row = AccessAttempt.objects.order_by("-id").first()
    assert row is not None
    assert (row.failures_since_start or 0) >= 5


@pytest.mark.django_db
def test_anonymize_user_cannot_login_bookings_remain():
    """F1.T3: после анонимизации вход невозможен; брони остаются привязаны к той же записи user pk."""
    from datetime import time as time_cls

    from apps.bookings.constants import BookingStatus
    from apps.bookings.models import Booking, TimeSlot
    from apps.stations.models import ServiceStation, WorkBay
    from django.utils import timezone

    client_u = User.objects.create_user(phone="+79991118888", password="x", email="cl@t.test")
    owner = User.objects.create_user(
        phone="+79991118889",
        password="x",
        email="ow@t.test",
        is_sto_owner=True,
        is_phone_verified=True,
    )
    st = ServiceStation.objects.create(
        owner=owner,
        name="СТО",
        slug="s-anon",
        address="ул. 1",
        is_active=True,
    )
    bay = WorkBay.objects.create(station=st, name="П1")
    slot = TimeSlot.objects.create(
        bay=bay,
        date=timezone.localdate(),
        start_time=time_cls(10, 0),
        end_time=time_cls(11, 0),
    )
    b = Booking.objects.create(
        client=client_u,
        station=st,
        slot=slot,
        car_info="X",
        contact_phone="+7",
        description="d",
        status=BookingStatus.COMPLETED,
    )
    pk = client_u.pk
    anonymize_user(client_u)
    client_u.refresh_from_db()
    assert not client_u.is_active
    assert client_u.phone.startswith("deleted_")
    assert Booking.objects.filter(pk=b.pk, client_id=pk).exists()
    assert not User.objects.filter(phone="+79991118888", is_active=True).exists()


@pytest.mark.django_db
def test_register_confirm_url_redirects_to_register():
    client = Client()
    r = client.get(reverse("users:register_confirm"))
    assert r.status_code == 302
    assert r.url == reverse("users:register")


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=False)
def test_register_full_flow_creates_consents():
    phone = "+79991119999"
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(reverse("users:register"), _register_post(phone, email="newreg@example.com"))
    assert r.status_code == 302
    assert r["Location"] == reverse("home")
    u = User.objects.get(phone=phone)
    assert u.is_phone_verified
    assert u.email_verified is False
    assert u.email_verification_token
    assert UserConsent.objects.filter(user=u).count() == 3


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=False)
def test_register_verify_email_link_confirms():
    from django.core import mail

    phone = "+79991119998"
    client = Client()
    client.get(reverse("users:register"))
    client.post(reverse("users:register"), _register_post(phone, email="verifyme@example.com"))
    u = User.objects.get(phone=phone)
    assert len(mail.outbox) == 1
    assert "МаБибип" in mail.outbox[0].subject
    token = u.email_verification_token
    uid = urlsafe_base64_encode(force_bytes(u.pk))
    url = reverse("users:verify_email", kwargs={"uidb64": uid, "token": token})
    r = client.get(url)
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.email_verified is True
    assert u.email_verification_token == ""


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=False)
def test_register_duplicate_phone_rejected():
    User.objects.create_user(phone="+79991110001", password="x")
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(
        reverse("users:register"),
        _register_post("+79991110001", email="dupphone@example.com"),
    )
    assert r.status_code == 200
    assert "уже зарегистрирован" in r.content.decode()


def _lite_post(phone: str, *, role: str = "driver", **extra):
    return {
        "phone": phone,
        "password1": "strong-pass-9",
        "password2": "strong-pass-9",
        "role": role,
        "accept_all_terms": "on",
        "recaptcha_token": "",
        **DRIVER_LITE_SECURITY_POST,
        **extra,
    }


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=True)
def test_register_driver_lite_without_email_succeeds():
    from django.core import mail

    phone = "+79991110002"
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(reverse("users:register"), _lite_post(phone))
    assert r.status_code == 302
    assert r["Location"] == reverse("home")
    u = User.objects.get(phone=phone)
    assert u.email_verified is True
    assert not (u.email or "").strip()
    assert UserConsent.objects.filter(user=u).count() == 3
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=False)
def test_register_driver_requires_email_when_lite_disabled():
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(reverse("users:register"), _register_post("+79991110003"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Укажите email" in body
    assert not User.objects.filter(phone="+79991110003").exists()


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=True)
def test_register_master_lite_requires_business_fields():
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(reverse("users:register"), _lite_post("+79991110004", role="master"))
    assert r.status_code == 200
    assert not User.objects.filter(phone="+79991110004").exists()


@pytest.mark.django_db
@override_settings(DRIVER_REGISTRATION_LITE=True)
def test_register_master_lite_without_email_succeeds():
    from apps.stations.models import ServiceStation

    phone = "+79991110005"
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(
        reverse("users:register"),
        _lite_post(
            phone,
            role="master",
            business_name="Иван Мастер",
            city_label="Москва",
        ),
    )
    assert r.status_code == 302
    u = User.objects.get(phone=phone)
    assert u.business_role == "master"
    assert u.sto_moderation_status == User.StoModerationStatus.APPROVED
    assert not (u.email or "").strip()
    st = ServiceStation.objects.get(owner=u)
    assert r.url == reverse("sto_owner:station_profile", kwargs={"slug": st.slug})
