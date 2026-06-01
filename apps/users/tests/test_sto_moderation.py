"""Премодерация регистрации владельца СТО (публичная заявка)."""

import re
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from apps.legal.models import DocumentKey, UserConsent, get_current_version
from apps.stations.constants import EXECUTOR_KIND_STO
from apps.stations.models import ServiceStation
from apps.users.tests.registration_helpers import REGISTRATION_SECURITY_POST

User = get_user_model()


def _grant_sto_offer_consent(user):
    ver = get_current_version(DocumentKey.STO_OFFER)
    if ver:
        UserConsent.objects.get_or_create(user=user, document_version=ver)


def _top_nav_html(content: str) -> str:
    """Верхняя панель (без нижней мобильной навигации и toast)."""
    m = re.search(
        r'<nav class="navbar navbar-expand-lg navbar-dark bg-dark">.*?</nav>',
        content,
        re.DOTALL,
    )
    return m.group(0) if m else ""


@pytest.mark.django_db
@override_settings(REGISTRATION_MODERATION_ENABLED=True)
@patch("apps.users.sto_moderation_mail.mail_admins")
def test_sto_register_creates_pending_owner_and_hidden_station(mock_mail):
    phone = "+79991333001"
    client = Client()
    r = client.post(
        reverse("users:sto_register"),
        data={
            "executor_kind": EXECUTOR_KIND_STO,
            "station_name": "Тест СТО",
            "city_label": "Москва",
            "phone": phone,
            "email": "sto_pending_1@example.com",
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r.status_code == 302
    assert r.url == reverse("sto_owner:pending_moderation")
    user = User.objects.get(phone=phone)
    assert user.is_sto_owner
    assert user.sto_moderation_status == User.StoModerationStatus.PENDING
    st = ServiceStation.objects.get(owner=user)
    assert st.is_active is False
    assert "Москва" in st.address
    mock_mail.assert_called_once()


@pytest.mark.django_db
def test_pending_owner_redirected_from_dashboard():
    phone = "+79991333002"
    user = User.objects.create_user(
        phone=phone,
        password="x",
        email="sto_p@example.com",
        is_sto_owner=True,
        is_phone_verified=True,
        sto_moderation_status=User.StoModerationStatus.PENDING,
    )
    c = Client()
    c.force_login(user)
    r = c.get(reverse("sto_owner:dashboard"))
    assert r.status_code == 302
    assert r.url == reverse("sto_owner:pending_moderation")


@pytest.mark.django_db
def test_sto_register_logged_in_client_shows_explainer_not_home():
    """Логированный клиент видит страницу заявки СТО с подсказкой выйти из аккаунта клиента."""
    client = User.objects.create_user(
        phone="+79991333004",
        password="x",
        email="client_only@example.com",
        is_sto_owner=False,
        is_phone_verified=True,
    )
    c = Client()
    c.force_login(client)
    r = c.get(reverse("users:sto_register"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "выйдите" in body.casefold() or "Выйти" in body


@pytest.mark.django_db
def test_approved_owner_can_open_dashboard_after_offer():
    phone = "+79991333003"
    user = User.objects.create_user(
        phone=phone,
        password="x",
        email="sto_ok@example.com",
        is_sto_owner=True,
        is_phone_verified=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
        contact_phone=phone,
    )
    _grant_sto_offer_consent(user)
    ServiceStation.objects.create(
        owner=user,
        name="СТО",
        slug="sto-mod-test",
        address="ул. 1",
        is_active=True,
    )
    c = Client()
    c.force_login(user)
    r = c.get(reverse("sto_owner:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_nav_home_shows_business_dropdown_for_approved_sto():
    """Одобренный владелец СТО видит отдельный пункт «Кабинет бизнеса», не только ЛК водителя."""
    user = User.objects.create_user(
        phone="+79991333098",
        password="x",
        email="sto_nav@example.com",
        is_sto_owner=True,
        is_phone_verified=True,
        sto_moderation_status=User.StoModerationStatus.APPROVED,
    )
    _grant_sto_offer_consent(user)
    c = Client()
    c.force_login(user)
    r = c.get(reverse("home"))
    assert r.status_code == 200
    body = r.content.decode()
    nav = _top_nav_html(body)
    assert "Кабинет бизнеса" in nav
    assert "Как клиент" in nav


@pytest.mark.django_db
@override_settings(REGISTRATION_MODERATION_ENABLED=False, RATELIMIT_ENABLE=False)
@patch("apps.users.sto_moderation_mail.mail_admins")
def test_sto_register_without_moderation_redirects_to_profile(mock_mail):
    phone = "+79991333005"
    client = Client()
    r = client.post(
        reverse("users:sto_register"),
        data={
            "executor_kind": EXECUTOR_KIND_STO,
            "station_name": "СТО без модерации",
            "city_label": "Москва",
            "phone": phone,
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r.status_code == 302
    user = User.objects.get(phone=phone)
    assert user.sto_moderation_status == User.StoModerationStatus.APPROVED
    st = ServiceStation.objects.get(owner=user)
    assert r.url == reverse("sto_owner:station_profile", kwargs={"slug": st.slug})
    mock_mail.assert_not_called()


@pytest.mark.django_db
def test_nav_home_no_business_dropdown_for_regular_client():
    """Обычный клиент не видит меню «Кабинет бизнеса»."""
    user = User.objects.create_user(
        phone="+79991333097",
        password="x",
        email="client_nav@example.com",
        is_sto_owner=False,
        is_phone_verified=True,
    )
    c = Client()
    c.force_login(user)
    r = c.get(reverse("home"))
    assert r.status_code == 200
    assert "Кабинет бизнеса" not in _top_nav_html(r.content.decode())
