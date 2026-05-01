from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.core.visitor_city import list_allowed_city_labels
from apps.legal.models import REGISTRATION_REQUIRED_KEYS, get_current_version
from apps.stations.constants import EXECUTOR_KIND_CHOICES
from apps.classifieds.models import AutoShopProfile

from .models import User
from .phone_utils import PhoneValidationError, normalize_to_e164


class EmailSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.setdefault("class", "form-control")


class EmailPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.setdefault("class", "form-control")
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")


class PhoneAuthenticationForm(AuthenticationForm):
    """Вход по телефону (USERNAME_FIELD) + пароль; капча v3 в шаблоне и form_valid view."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Телефон"
        for name in ("username", "password"):
            self.fields[name].widget.attrs.setdefault("class", "form-control")
            ac = "username" if name == "username" else "current-password"
            self.fields[name].widget.attrs.setdefault("autocomplete", ac)
        self.fields["username"].widget.attrs.setdefault("autocomplete", "tel-national")

    def clean_username(self):
        raw = self.cleaned_data.get("username", "")
        try:
            return normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise ValidationError(str(e)) from e


class RecaptchaTokenMixin(forms.Form):
    """Скрытое поле токена; фронт заполняет через grecaptcha.execute (v3)."""

    recaptcha_token = forms.CharField(required=False, widget=forms.HiddenInput)


class RegistrationSecurityMixin(forms.Form):
    """Honeypot + подтверждение номера (антиспам, ТЗ МаБибип)."""

    website_url = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "aria-hidden": "true",
                "style": "display:none",
            },
        ),
    )
    phone_owner_confirm = forms.BooleanField(
        required=True,
        label="Это мой номер телефона",
        error_messages={
            "required": "Подтвердите, что указанный телефон принадлежит вам.",
        },
    )

    def clean(self):
        data = super().clean()
        if (data.get("website_url") or "").strip():
            raise ValidationError("Подача заявки отклонена системой защиты от спама.")
        return data


class RegisterForm(RecaptchaTokenMixin, RegistrationSecurityMixin, forms.Form):
    """Регистрация: телефон + пароль, без SMS-кода."""

    phone = forms.CharField(label="Телефон", max_length=20)
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Пароль ещё раз",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    email = forms.EmailField(
        label="Email (необязательно)",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )
    accept_privacy = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо принять политику конфиденциальности."},
    )
    accept_user_agreement = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо принять пользовательское соглашение."},
    )
    accept_pd_consent = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо дать согласие на обработку персональных данных."},
    )

    field_order = [
        "phone",
        "password1",
        "password2",
        "email",
        "website_url",
        "phone_owner_confirm",
        "accept_privacy",
        "accept_user_agreement",
        "accept_pd_consent",
        "recaptcha_token",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.setdefault("class", "form-control")
        self.fields["phone"].widget.attrs.setdefault("autocomplete", "tel-national")

    def clean_phone(self):
        raw = self.cleaned_data["phone"]
        try:
            phone = normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise ValidationError(str(e)) from e
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("Пользователь с таким номером уже зарегистрирован.")
        return phone

    def clean_email(self):
        e = self.cleaned_data.get("email")
        if not e:
            return None
        e = e.strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")
        return e

    def clean_password1(self):
        p1 = self.cleaned_data.get("password1")
        if not p1:
            return p1
        phone = self.cleaned_data.get("phone") or ""
        validate_password(p1, user=User(phone=phone))
        return p1

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Пароли не совпадают.")
        missing_docs = [k for k in REGISTRATION_REQUIRED_KEYS if get_current_version(k) is None]
        if missing_docs:
            raise ValidationError(
                "Юридические документы временно недоступны. "
                "Попробуйте позже или обратитесь в поддержку.",
            )
        return data


class RoleRegisterForm(RegisterForm):
    field_order = [
        "role",
        "phone",
        "password1",
        "password2",
        "email",
        "business_name",
        "city_label",
        "autoshop_kind",
        "website_url",
        "phone_owner_confirm",
        "accept_privacy",
        "accept_user_agreement",
        "accept_pd_consent",
        "recaptcha_token",
    ]

    role = forms.ChoiceField(
        label="Роль",
        choices=User.BusinessRole.choices,
        widget=forms.HiddenInput,
        required=True,
    )
    business_name = forms.CharField(
        label="Название",
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

    def clean(self):
        data = super().clean()
        role = (data.get("role") or User.BusinessRole.DRIVER).strip()
        if role not in dict(User.BusinessRole.choices):
            raise ValidationError("Выберите роль.")
        data["role"] = role
        if role != User.BusinessRole.DRIVER:
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


class StoRegistrationForm(RecaptchaTokenMixin, RegistrationSecurityMixin, forms.Form):
    """Публичная регистрация исполнителя (СТО / частный мастер) с премодерацией."""

    field_order = [
        "executor_kind",
        "station_name",
        "city_label",
        "phone",
        "email",
        "password1",
        "password2",
        "website_url",
        "phone_owner_confirm",
        "accept_privacy",
        "accept_user_agreement",
        "accept_pd_consent",
        "recaptcha_token",
    ]

    executor_kind = forms.ChoiceField(
        label="Тип",
        choices=EXECUTOR_KIND_CHOICES,
        widget=forms.RadioSelect,
    )
    station_name = forms.CharField(
        label="Название сервиса или ваше имя",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    city_label = forms.CharField(label="Город", max_length=120)
    phone = forms.CharField(label="Телефон", max_length=20)
    email = forms.EmailField(
        label="Электронная почта",
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Пароль ещё раз",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    accept_privacy = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо принять политику конфиденциальности."},
    )
    accept_user_agreement = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо принять пользовательское соглашение."},
    )
    accept_pd_consent = forms.BooleanField(
        required=True,
        label="",
        error_messages={"required": "Необходимо дать согласие на обработку персональных данных."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.setdefault("class", "form-control")
        self.fields["phone"].widget.attrs.setdefault("autocomplete", "tel-national")
        labels = list_allowed_city_labels()
        if labels:
            self.fields["city_label"] = forms.ChoiceField(
                label="Город",
                choices=[("", "— выберите город —")] + [(x, x) for x in sorted(set(labels))],
                widget=forms.Select(attrs={"class": "form-select", "size": "8"}),
            )

    def clean_phone(self):
        raw = self.cleaned_data["phone"]
        try:
            phone = normalize_to_e164(raw)
        except PhoneValidationError as e:
            raise ValidationError(str(e)) from e
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("Пользователь с таким номером уже зарегистрирован.")
        return phone

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")
        return e

    def clean_city_label(self):
        raw = (self.cleaned_data.get("city_label") or "").strip()
        if not raw:
            raise ValidationError("Укажите город.")
        allowed = list_allowed_city_labels()
        if allowed and raw not in allowed:
            raise ValidationError("Выберите город из списка.")
        return raw

    def clean_password1(self):
        p1 = self.cleaned_data.get("password1")
        if not p1:
            return p1
        phone = self.cleaned_data.get("phone") or ""
        validate_password(p1, user=User(phone=phone))
        return p1

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Пароли не совпадают.")
        missing_docs = [k for k in REGISTRATION_REQUIRED_KEYS if get_current_version(k) is None]
        if missing_docs:
            raise ValidationError(
                "Юридические документы временно недоступны. "
                "Попробуйте позже или обратитесь в поддержку.",
            )
        return data


class AdminUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("phone", "email")

    def clean_email(self):
        e = self.cleaned_data.get("email")
        if not e:
            return None
        return e.strip().lower()


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class AccountDeleteForm(forms.Form):
    """Подтверждение осознанного удаления (дополнительная кнопка POST)."""

    confirm = forms.BooleanField(
        required=True,
        label="Я понимаю, что персональные данные будут обезличены",
    )
