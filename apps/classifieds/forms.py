from __future__ import annotations

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms.widgets import FileInput
from django.utils import timezone
from django.utils.text import Truncator

from PIL import Image

from apps.core.visitor_city import list_allowed_city_labels
from apps.stations.models import CarBrand

from .text_moderation import validate_listing_text
from .models import (
    Ad,
    AdKind,
    AutoShopBranch,
    AutoShopProfile,
    CarBodyType,
    CarDrive,
    CarFuel,
    CarSteering,
    CarTransmission,
    PartCategory,
    SellerReview,
)


class MultiFileInput(FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    FileField, который принимает список файлов (multiple) и возвращает list[UploadedFile].
    Django по умолчанию ожидает один файл; для витрины объявлений нам нужно несколько.
    """

    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned: list = []
        errors: list[ValidationError] = []
        for item in data:
            try:
                cleaned.append(super().clean(item, initial))
            except ValidationError as e:
                errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)
        return cleaned


class AdForm(forms.ModelForm):
    photos = MultipleFileField(
        label="Фото",
        required=False,
        widget=MultiFileInput(attrs={"multiple": True, "class": "form-control"}),
        help_text="До 15 фото за раз (JPEG, PNG, WEBP; каждый файл до 5 МБ).",
    )

    class Meta:
        model = Ad
        fields = [
            "kind",
            "title",
            "price",
            "city_label",
            "description",
            "is_published",
            "part_category",
            "part_brand",
            "condition",
            "car_brand",
            "car_model",
            "car_year",
            "car_mileage_km",
            "car_generation",
            "car_engine_l",
            "car_power_hp",
            "car_transmission",
            "car_fuel",
            "car_drive",
            "car_body_type",
            "car_color",
            "car_steering",
            "car_vin",
            "car_owners_count",
            "car_not_crashed",
        ]
        widgets = {
            "kind": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "city_label": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "part_category": forms.Select(attrs={"class": "form-select"}),
            "part_brand": forms.Select(attrs={"class": "form-select"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "car_brand": forms.Select(attrs={"class": "form-select"}),
            "car_model": forms.TextInput(attrs={"class": "form-control"}),
            "car_year": forms.NumberInput(attrs={"class": "form-control"}),
            "car_mileage_km": forms.NumberInput(attrs={"class": "form-control"}),
            "car_generation": forms.TextInput(attrs={"class": "form-control"}),
            "car_engine_l": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "car_power_hp": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "car_transmission": forms.Select(attrs={"class": "form-select"}),
            "car_fuel": forms.Select(attrs={"class": "form-select"}),
            "car_drive": forms.Select(attrs={"class": "form-select"}),
            "car_body_type": forms.Select(attrs={"class": "form-select"}),
            "car_color": forms.TextInput(attrs={"class": "form-control"}),
            "car_steering": forms.Select(attrs={"class": "form-select"}),
            "car_vin": forms.TextInput(attrs={"class": "form-control", "maxlength": "32"}),
            "car_owners_count": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "car_not_crashed": forms.NullBooleanSelect(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self._moderation_flagged = False
        self._moderation_reason = ""
        self.fields["part_category"].queryset = PartCategory.objects.order_by("sort_order", "name")
        self.fields["part_brand"].queryset = CarBrand.objects.order_by("-is_popular", "sort_order", "name")
        self.fields["car_brand"].queryset = CarBrand.objects.order_by("-is_popular", "sort_order", "name")
        labels = list_allowed_city_labels()
        if labels:
            # Видимый listbox: выпадающий <select class="form-select"> в Chromium/Яндекс даёт пустое меню.
            # «size» + form-control — строки городов всегда на экране (прокрутка внутри списка).
            rows = min(len(labels) + 1, 14)
            rows = max(rows, 8)
            self.fields["city_label"].widget = forms.Select(
                attrs={
                    "class": "form-control pm-city-listbox",
                    "size": str(rows),
                    "aria-label": "Город объявления",
                }
            )
            self.fields["city_label"].choices = [("", "— выберите город —")] + [(x, x) for x in labels]
        for _fname, choices in (
            ("car_transmission", CarTransmission),
            ("car_fuel", CarFuel),
            ("car_drive", CarDrive),
            ("car_body_type", CarBodyType),
            ("car_steering", CarSteering),
        ):
            self.fields[_fname].choices = [("", "— не указано —")] + list(choices.choices)

    def clean_city_label(self):
        raw = (self.cleaned_data.get("city_label") or "").strip()
        if not raw:
            raise ValidationError("Укажите город.")
        allowed = list_allowed_city_labels()
        if allowed and raw not in allowed:
            raise ValidationError("Выберите город из списка.")
        return raw

    def clean_car_vin(self):
        raw = (self.cleaned_data.get("car_vin") or "").strip().upper().replace(" ", "")
        if len(raw) > 32:
            raise ValidationError("VIN не длиннее 32 символов.")
        return raw

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind == AdKind.PART:
            cleaned["car_brand"] = None
            cleaned["car_model"] = ""
            cleaned["car_year"] = None
            cleaned["car_mileage_km"] = None
            cleaned["car_generation"] = ""
            cleaned["car_engine_l"] = None
            cleaned["car_power_hp"] = None
            cleaned["car_transmission"] = ""
            cleaned["car_fuel"] = ""
            cleaned["car_drive"] = ""
            cleaned["car_body_type"] = ""
            cleaned["car_color"] = ""
            cleaned["car_steering"] = ""
            cleaned["car_vin"] = ""
            cleaned["car_owners_count"] = None
            cleaned["car_not_crashed"] = None
        elif kind == AdKind.CAR:
            cleaned["part_category"] = None
            cleaned["part_brand"] = None
            cleaned["condition"] = ""

        # Антифрод: контакты/мессенджеры/email в тексте объявления → на модерацию.
        title = (cleaned.get("title") or "").strip()
        desc = (cleaned.get("description") or "").strip()
        reasons = sorted(set(validate_listing_text(title) + validate_listing_text(desc)))
        if reasons:
            cleaned["is_published"] = False
            self._moderation_flagged = True
            self._moderation_reason = "Контакты в тексте объявления"
            days = int(getattr(settings, "CONTACTS_STRICT_DAYS_FOR_NEW_USERS", 7))
            u = getattr(self, "user", None)
            if u and getattr(u, "date_joined", None):
                age_days = (timezone.now() - u.date_joined).days
                if age_days < days:
                    self.add_error(
                        None,
                        "Для новых аккаунтов запрещено указывать контакты в тексте. Удалите телефон/мессенджеры/email и попробуйте снова.",
                    )
                # Для «старых» аккаунтов не блокируем форму: просто отправляем на модерацию (pending).
        return cleaned

    def save(self, commit=True):
        obj: Ad = super().save(commit=False)
        if getattr(self, "_moderation_flagged", False):
            obj.moderation_status = Ad.ModerationStatus.PENDING
            obj.moderation_reason = (getattr(self, "_moderation_reason", "") or "")[:300]
        else:
            # если пользователь «починил» текст, возвращаем в OK
            obj.moderation_status = Ad.ModerationStatus.OK
            obj.moderation_reason = ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj

    def clean_photos(self):
        files = self.cleaned_data.get("photos") or []
        if not files:
            return []

        max_files = 15
        if len(files) > max_files:
            raise ValidationError(f"Можно загрузить не более {max_files} фото за раз.")

        max_bytes = 5 * 1024 * 1024
        ext_validator = FileExtensionValidator(
            allowed_extensions=("jpg", "jpeg", "png", "webp"),
            message="Допустимы только изображения JPG, PNG или WEBP.",
        )

        for f in files:
            if getattr(f, "size", 0) and f.size > max_bytes:
                raise ValidationError(
                    f"Файл слишком большой: {Truncator(f.name).chars(40)}. Максимум 5MB."
                )
            ext_validator(f)
            try:
                pos = f.tell()
            except Exception:
                pos = None
            try:
                img = Image.open(f)
                img.verify()
            except Exception:
                raise ValidationError(
                    f"Файл не похож на изображение: {Truncator(f.name).chars(40)}."
                )
            finally:
                try:
                    if pos is not None:
                        f.seek(pos)
                    else:
                        f.seek(0)
                except Exception:
                    pass
        return files


class AdUnpublishForm(forms.Form):
    reason = forms.ChoiceField(
        label="Причина",
        choices=Ad.UnpublishReason.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reason_text = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Опишите причину"}),
        max_length=300,
    )

    def clean(self):
        cleaned = super().clean()
        reason = (cleaned.get("reason") or "").strip()
        txt = (cleaned.get("reason_text") or "").strip()
        if reason == Ad.UnpublishReason.OTHER and not txt:
            self.add_error("reason_text", "Укажите причину (в свободной форме).")
        cleaned["reason_text"] = txt
        return cleaned


class AutoShopProfileForm(forms.ModelForm):
    class Meta:
        model = AutoShopProfile
        fields = ["name", "city_label", "address", "description", "contact_phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "city_label": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
        }


class AutoShopBranchForm(forms.ModelForm):
    class Meta:
        model = AutoShopBranch
        fields = ["name", "city_label", "address", "contact_phone", "work_hours"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "city_label": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "work_hours": forms.TextInput(attrs={"class": "form-control"}),
        }


class SellerReviewForm(forms.ModelForm):
    class Meta:
        model = SellerReview
        fields = ["rating", "text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Расскажите, как прошло общение или сделка (необязательно)",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rating"].widget = forms.RadioSelect(
            choices=[(i, f"{i} ★") for i in range(1, 6)],
            attrs={"class": "d-flex flex-wrap gap-3"},
        )
        self.fields["text"].required = False

