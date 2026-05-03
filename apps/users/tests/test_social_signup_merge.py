"""Слияние соцаккаунта при вводе email на /oauth/signup/ с уже существующим пользователем."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from allauth.socialaccount.models import SocialAccount, SocialLogin

from apps.users.social_signup_form import TachkiSocialSignupForm

User = get_user_model()


@pytest.mark.django_db
def test_social_signup_form_accepts_email_of_existing_user():
    User.objects.create_user(phone="+79995550333", password="x", email="merge-social@example.com")
    placeholder = User(email=None, phone="oauth_vk_aaaaaaaaaaaaaaaa")
    account = SocialAccount(provider="vk", uid="merge-test-uid-1", extra_data={})
    sociallogin = SocialLogin(user=placeholder, account=account)

    form = TachkiSocialSignupForm(sociallogin=sociallogin, data={"email": "merge-social@example.com"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["email"] == "merge-social@example.com"
