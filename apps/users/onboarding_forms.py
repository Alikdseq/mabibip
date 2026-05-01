from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.classifieds.models import AutoShopProfile
from apps.core.visitor_city import list_allowed_city_labels
from apps.legal.models import REGISTRATION_REQUIRED_KEYS, get_current_version

from .phone_utils import PhoneValidationError, normalize_to_e164

User = get_user_model()


class OAuthOnboardingForm(forms.Form):
    role = forms.ChoiceField(
        label="Роль",
        choices=User.BusinessRole.choices,
        widget=forms.HiddenInput,
        required=True,
    )
    contact_phone = forms.CharField(
        label="Телефон для связи",
        max_length=32,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel-national"}),
        required=True,
    )
    business_name = forms.CharField(
        label="Название / имя",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    city_label = forms.CharField(label="Город", max_length=120, required=False)
    autoshop_kind = forms.ChoiceField(
        label="Тип автомагазина",
        required=False,
        choices=AutoShopProfile.Kind.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    accept_privacy = forms.BooleanField(
        required=False,
        label="",
        error_messages={"required": "Необходимо принять политику конфиденциальности."},
    )
    accept_user_agreement = forms.BooleanField(
        required=False,
        label="",
        error_messages={"required": "Необходимо принять пользовательское соглашение."},
    )
    accept_pd_consent = forms.BooleanField(
        required=False,
        label="",
        error_messages={"required": "Необходимо дать согласие на обработку персональных данных."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = list_allowed_city_labels()
        if labels:
            self.fields["city_label"] = forms.ChoiceField(
                label="Город",
                required=False,
                choices=[("", "— выберите город —")] + [(x, x) for x in sorted(set(labels))],
                widget=forms.Select(attrs={"class": "form-select", "size": "8"}),
            )

    def clean_contact_phone(self) -> str:
        raw = self.cleaned_data.get("contact_phone") or ""
        try:
            return normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise ValidationError(str(e)) from e

    def clean(self):
        data = super().clean()
        role = (data.get("role") or User.BusinessRole.DRIVER).strip()
        if role not in dict(User.BusinessRole.choices):
            raise ValidationError("Выберите роль.")
        data["role"] = role

        missing_docs = [k for k in REGISTRATION_REQUIRED_KEYS if get_current_version(k) is None]
        if missing_docs:
            raise ValidationError(
                "Юридические документы временно недоступны. "
                "Попробуйте позже или обратитесь в поддержку.",
            )

        if role != User.BusinessRole.DRIVER:
            if not data.get("accept_privacy"):
                self.add_error("accept_privacy", "Необходимо принять политику конфиденциальности.")
            if not data.get("accept_user_agreement"):
                self.add_error("accept_user_agreement", "Необходимо принять пользовательское соглашение.")
            if not data.get("accept_pd_consent"):
                self.add_error("accept_pd_consent", "Необходимо дать согласие на обработку персональных данных.")

            bn = (data.get("business_name") or "").strip()
            if not bn:
                raise ValidationError("Укажите название/имя для бизнеса.")
            city = (data.get("city_label") or "").strip()
            if not city:
                raise ValidationError("Укажите город.")
        if role == User.BusinessRole.AUTOSHOP:
            k = (data.get("autoshop_kind") or "").strip()
            allowed = {x for x, _ in AutoShopProfile.Kind.choices}
            if k not in allowed:
                raise ValidationError("Выберите тип: автомагазин / разборка / автосалон.")
        return data

