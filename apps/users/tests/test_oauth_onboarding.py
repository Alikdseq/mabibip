from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from apps.classifieds.models import AutoShopProfile
from apps.stations.models import ServiceStation
from apps.users.models import User
from apps.users.allauth_adapters import TachkiSocialAccountAdapter


@pytest.mark.django_db
def test_key_action_blocked_until_onboarding_complete(client):
    u = User.objects.create_user(phone="+79995550001", password="x")
    client.force_login(u)
    r = client.get(reverse("classifieds_api:ad_reveal_phone", kwargs={"pk": 999999}))
    assert r.status_code == 403
    data = r.json()
    assert data["ok"] is False
    assert "redirect_url" in data
    assert data["redirect_url"].startswith("/cabinet/profile/")


@pytest.mark.django_db
def test_complete_profile_driver_saves_phone_and_role(client):
    u = User.objects.create_user(phone="+79995550011", password="x")
    client.force_login(u)
    url = reverse("users:complete_profile")
    r = client.post(
        url,
        data={
            "role": User.BusinessRole.DRIVER,
            "contact_phone": "8 (999) 555-00-11",
        },
    )
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.business_role == User.BusinessRole.DRIVER
    assert u.business_role_chosen is True
    assert u.contact_phone == "+79995550011"


@pytest.mark.django_db
def test_oauth_process_login_requires_existing_email():
    User.objects.create_user(phone="+79995550999", password="x", email="exist@example.com")
    rf = RequestFactory()

    # Existing email: allowed
    req_ok = rf.get("/oauth/google/login/", {"process": "login"})
    setattr(req_ok, "session", {})
    setattr(req_ok, "_messages", FallbackStorage(req_ok))
    sociallogin_ok = SimpleNamespace(user=User(email="exist@example.com"))
    assert TachkiSocialAccountAdapter().is_open_for_signup(req_ok, sociallogin_ok) is True

    # Missing user by email: forbidden
    req_no = rf.get("/oauth/google/login/", {"process": "login"})
    setattr(req_no, "session", {})
    setattr(req_no, "_messages", FallbackStorage(req_no))
    sociallogin_no = SimpleNamespace(user=User(email="absent@example.com"))
    assert TachkiSocialAccountAdapter().is_open_for_signup(req_no, sociallogin_no) is False

    # process=signup: allowed
    req_su = rf.get("/oauth/google/login/", {"process": "signup"})
    setattr(req_su, "session", {})
    setattr(req_su, "_messages", FallbackStorage(req_su))
    sociallogin_su = SimpleNamespace(user=User(email="new@example.com"))
    assert TachkiSocialAccountAdapter().is_open_for_signup(req_su, sociallogin_su) is True


@pytest.mark.django_db
def test_complete_profile_autoshop_creates_profile(client):
    u = User.objects.create_user(phone="+79995550101", password="x")
    client.force_login(u)
    r = client.post(
        reverse("users:complete_profile"),
        data={
            "role": User.BusinessRole.AUTOSHOP,
            "contact_phone": "+7 (999) 555-01-01",
            "business_name": "Shop 1",
            "city_label": "Владикавказ",
            "autoshop_kind": AutoShopProfile.Kind.SHOP,
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
        },
    )
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.business_role_chosen is True
    assert u.is_sto_owner is True
    assert AutoShopProfile.objects.filter(owner=u).exists()
    shop = AutoShopProfile.objects.get(owner=u)
    assert shop.contact_phone == u.contact_phone


@pytest.mark.django_db
def test_complete_profile_master_creates_station_pending(client):
    u = User.objects.create_user(phone="+79995550201", password="x")
    client.force_login(u)
    r = client.post(
        reverse("users:complete_profile"),
        data={
            "role": User.BusinessRole.MASTER,
            "contact_phone": "+79995550201",
            "business_name": "Master 1",
            "city_label": "Владикавказ",
            "accept_privacy": "on",
            "accept_user_agreement": "on",
            "accept_pd_consent": "on",
        },
    )
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.business_role == User.BusinessRole.MASTER
    assert u.business_role_chosen is True
    assert u.is_sto_owner is True
    assert u.sto_moderation_status == User.StoModerationStatus.PENDING
    assert ServiceStation.objects.filter(owner=u).exists()

