"""Фаза F0: юридический фундамент — регистрация, согласия, архив, middleware СТО."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.users.tests.registration_helpers import REGISTRATION_SECURITY_POST

from apps.legal.models import (
    DocumentKey,
    LegalDocumentVersion,
    UserConsent,
    get_current_version,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def _disable_ratelimit_in_tests(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.mark.django_db
def test_register_without_phone_invalid():
    client = Client()
    client.get(reverse("users:register"))
    r = client.post(
        reverse("users:register"),
        data={
            "role": User.BusinessRole.DRIVER,
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r.status_code == 200


@pytest.mark.django_db
def test_register_full_saves_three_consents():
    phone = "+79991113333"
    client = Client()
    client.get(reverse("users:register"))
    r2 = client.post(
        reverse("users:register"),
        data={
            "role": User.BusinessRole.DRIVER,
            "phone": phone,
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "email": "f0consents@example.com",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r2.status_code == 302
    user = User.objects.get(phone=phone)
    qs = UserConsent.objects.filter(user=user)
    assert qs.count() == 3
    keys = {c.document_version.key for c in qs}
    assert keys == {
        DocumentKey.PRIVACY,
        DocumentKey.USER_AGREEMENT,
        DocumentKey.PD_CONSENT,
    }


@pytest.mark.django_db
def test_register_fails_when_privacy_doc_missing():
    phone = "+79991113344"
    client = Client()
    client.get(reverse("users:register"))
    LegalDocumentVersion.objects.filter(key=DocumentKey.PRIVACY).delete()
    r = client.post(
        reverse("users:register"),
        data={
            "role": User.BusinessRole.DRIVER,
            "phone": phone,
            "password1": "strong-pass-9",
            "password2": "strong-pass-9",
            "email": "f0privacy@example.com",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
            "recaptcha_token": "",
            **REGISTRATION_SECURITY_POST,
        },
    )
    assert r.status_code == 200
    assert "Юридические документы" in r.content.decode()


@pytest.mark.django_db
def test_legal_archive_lists_versions():
    client = Client()
    r = client.get(reverse("legal:archive"))
    assert r.status_code == 200
    assert LegalDocumentVersion.objects.exists()


@pytest.mark.django_db
def test_legal_document_current_renders():
    client = Client()
    r = client.get(reverse("legal:document", kwargs={"key": DocumentKey.PRIVACY}))
    assert r.status_code == 200


@pytest.mark.django_db
def test_sto_owner_redirected_to_consent_until_accepted():
    owner = User.objects.create_user(
        phone="+79991113355",
        password="x",
        email="sto@example.com",
        is_sto_owner=True,
        is_active=True,
        is_phone_verified=True,
    )
    sto_ver = get_current_version(DocumentKey.STO_OFFER)
    assert sto_ver is not None
    UserConsent.objects.filter(user=owner, document_version=sto_ver).delete()

    client = Client()
    client.force_login(owner)
    r = client.get(reverse("sto_owner:dashboard"))
    assert r.status_code == 302
    assert r["Location"] == reverse("legal:sto_consent")


@pytest.mark.django_db
def test_sto_consent_post_allows_dashboard():
    owner = User.objects.create_user(
        phone="+79991113366",
        password="x",
        email="sto2@example.com",
        is_sto_owner=True,
        is_active=True,
        is_phone_verified=True,
        contact_phone="+79991113366",
    )
    sto_ver = get_current_version(DocumentKey.STO_OFFER)
    UserConsent.objects.filter(user=owner, document_version=sto_ver).delete()

    client = Client()
    client.force_login(owner)
    url = reverse("legal:sto_consent")
    r = client.get(url)
    assert r.status_code == 200
    r = client.post(url, data={"accept_sto_offer": "on"})
    assert r.status_code == 302
    assert UserConsent.objects.filter(user=owner, document_version=sto_ver).exists()
    r2 = client.get(reverse("sto_owner:dashboard"))
    assert r2.status_code == 200
