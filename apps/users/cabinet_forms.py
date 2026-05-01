"""Формы личного кабинета клиента (фаза B)."""

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.users.models import ContactPhoneChangeRequest, SavedCar
from apps.users.phone_utils import PhoneValidationError, normalize_to_e164

User = get_user_model()

_CLIENT_AVATAR_MAX_BYTES = int(getattr(settings, "USER_AVATAR_MAX_BYTES", 5 * 1024 * 1024))


class ClientProfileForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._request_user = user
        # Контактный телефон после заполнения меняется только через заявку с одобрением админом.
        inst_phone = (getattr(self.instance, "contact_phone", "") or "").strip()
        if inst_phone and not bool(getattr(user, "is_staff", False)):
            f = self.fields.get("contact_phone")
            if f:
                f.disabled = True
                f.help_text = "Чтобы изменить телефон, подайте заявку на смену ниже."

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_phone", "avatar")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "tel-national"},
            ),
            "avatar": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp",
                },
            ),
        }

    def clean_avatar(self):
        f = self.cleaned_data.get("avatar")
        if not f:
            return f
        if getattr(f, "size", 0) and f.size > _CLIENT_AVATAR_MAX_BYTES:
            raise forms.ValidationError(
                f"Файл слишком большой — не более {_CLIENT_AVATAR_MAX_BYTES // (1024 * 1024)} МБ.",
            )
        return f

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip() or None
        if email:
            qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Этот email уже привязан к другому аккаунту.")
        return email

    def clean_contact_phone(self):
        # Если поле выключено — сохраняем текущее значение.
        if self.fields.get("contact_phone") and self.fields["contact_phone"].disabled:
            return (getattr(self.instance, "contact_phone", "") or "").strip()

        raw = (self.cleaned_data.get("contact_phone") or "").strip()
        if not raw:
            return ""
        try:
            return normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise forms.ValidationError(str(e)) from e


class ContactPhoneChangeRequestForm(forms.ModelForm):
    new_phone = forms.CharField(
        label="Новый телефон для связи",
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel-national"}),
    )

    class Meta:
        model = ContactPhoneChangeRequest
        fields = ("new_phone", "reason")
        widgets = {
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": "500"}),
        }

    def clean_new_phone(self) -> str:
        raw = (self.cleaned_data.get("new_phone") or "").strip()
        try:
            return normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise forms.ValidationError(str(e)) from e


class SavedCarForm(forms.ModelForm):
    class Meta:
        model = SavedCar
        fields = ("license_plate", "brand_model", "vin")
        widgets = {
            "license_plate": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "А123ВС777"},
            ),
            "brand_model": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Toyota Camry"},
            ),
            "vin": forms.TextInput(attrs={"class": "form-control", "placeholder": "Необязательно"}),
        }

    def clean_license_plate(self):
        return (self.cleaned_data.get("license_plate") or "").strip().upper()
