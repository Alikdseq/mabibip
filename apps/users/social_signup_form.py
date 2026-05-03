"""
Форма дозаполнения email после OAuth (`/oauth/signup/`).

Стандартный `SignupForm` из allauth вызывает `validate_unique_email` → при занятом email
выдаётся ошибка до `save_user`, хотя у нас в `TachkiSocialAccountAdapter.save_user` уже есть
слияние через `sociallogin.connect(existing)` при совпадении email с пользователем Google /
регистрации по телефону.

Если введённый email принадлежит существующему `User`, пропускаем конфликт на уровне формы,
чтобы дошло до адаптера.

Примечание по безопасности: пользователь уже завершил OAuth у провайдера; строгая проверка
владения почтой при ручном вводе — возможное усиление отдельным потоком верификации.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.forms import SignupForm as AllauthSocialSignupForm


class TachkiSocialSignupForm(AllauthSocialSignupForm):
    def validate_unique_email(self, value):
        User = get_user_model()
        acc_adapter = get_account_adapter()
        v = acc_adapter.clean_email((value or "").strip())
        if not v:
            return v

        if User.objects.filter(email__iexact=v).exists():
            self.account_already_exists = False
            return acc_adapter.validate_unique_email(v)

        try:
            return super().validate_unique_email(value)
        except forms.ValidationError:
            prov = getattr(self.sociallogin, "provider", None)
            label = getattr(prov, "name", None) if prov else None
            if not label:
                label = getattr(self.sociallogin.account, "provider", "") or "oauth"
            raise get_social_adapter().validation_error("email_taken", label)
