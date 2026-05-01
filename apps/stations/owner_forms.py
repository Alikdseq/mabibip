from django import forms
from django.forms import ValidationError, inlineformset_factory
from django.utils import timezone

from apps.bookings.models import TimeSlot
from apps.stations.models import (
    CarBrand,
    District,
    ServiceCategory,
    ServiceSection,
    ServiceStation,
    StationServiceOffer,
    WorkBay,
)
from apps.users.phone_utils import PhoneValidationError, normalize_to_e164


class TimeSlotCreateForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ("bay", "date", "start_time", "end_time", "is_available")
        widgets = {
            "bay": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "end_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "is_available": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, owner, **kwargs):
        self._owner = owner
        super().__init__(*args, **kwargs)
        self.fields["bay"].queryset = WorkBay.objects.filter(station__owner=owner).select_related(
            "station"
        )
        self.fields["bay"].label_from_instance = lambda obj: f"{obj.station.name} — {obj.name}"

    def clean_bay(self):
        bay = self.cleaned_data["bay"]
        if bay.station.owner_id != self._owner.pk:
            raise forms.ValidationError("Недопустимый пост.")
        return bay

    def clean(self):
        cleaned_data = super().clean()
        d = cleaned_data.get("date")
        st = cleaned_data.get("start_time")
        if d is not None and st is not None and d == timezone.localdate():
            if st <= timezone.localtime().time():
                raise ValidationError(
                    "Для сегодня укажите время начала позже текущего.",
                    code="slot_start_not_future",
                )
        return cleaned_data


class TimeSlotQuickTodayForm(TimeSlotCreateForm):
    """Компактная форма для дашборда: дата и «доступно» задаются скрытыми полями (только сегодня)."""

    class Meta(TimeSlotCreateForm.Meta):
        widgets = {
            **TimeSlotCreateForm.Meta.widgets,
            "date": forms.HiddenInput(),
            "is_available": forms.HiddenInput(),
        }

    def __init__(self, *args, owner, today, **kwargs):
        super().__init__(*args, owner=owner, **kwargs)
        self.fields["date"].initial = today
        self.fields["is_available"].initial = True


class WorkBayCreateForm(forms.ModelForm):
    class Meta:
        model = WorkBay
        fields = ("station", "name")
        widgets = {
            "station": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": "50"}),
        }

    def __init__(self, *args, owner, **kwargs):
        self._owner = owner
        super().__init__(*args, **kwargs)
        self.fields["station"].queryset = ServiceStation.objects.filter(owner=owner).order_by(
            "name", "pk"
        )
        self.fields["station"].empty_label = None

    def clean_station(self):
        station = self.cleaned_data["station"]
        if station.owner_id != self._owner.pk:
            raise forms.ValidationError("Недопустимая станция.")
        return station


class StationMasterCreateForm(forms.ModelForm):
    class Meta:
        model = ServiceStation
        fields = (
            "name",
            "tagline",
            "experience_years",
            "master_bio",
            "avatar",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "experience_years": forms.NumberInput(attrs={"class": "form-control"}),
            "master_bio": forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
        }


class StationMasterQuickEditForm(StationMasterCreateForm):
    """Быстрое редактирование базовых полей мастера из списка."""

    pass


class StationMasterFullCreateForm(forms.ModelForm):
    """
    Полная форма мастера автосервиса: максимально близка к публичной карточке «частного мастера»,
    но без самостоятельных контактов (они будут вести в автосервис-родитель).
    """

    class Meta:
        model = ServiceStation
        fields = (
            "name",
            "tagline",
            "experience_years",
            "master_bio",
            "avatar",
            "description_short",
            "description",
            "service_sections",
            "categories",
            "car_brands",
            "car_brands_all",
            "certified_partner",
            "license_held",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": "200"}),
            "tagline": forms.TextInput(attrs={"class": "form-control", "maxlength": "220"}),
            "experience_years": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "master_bio": forms.Textarea(attrs={"class": "form-control", "rows": "4"}),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description_short": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "service_sections": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "categories": forms.SelectMultiple(attrs={"class": "form-select", "size": "10"}),
            "car_brands": forms.SelectMultiple(attrs={"class": "form-select", "size": "12"}),
            "car_brands_all": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "certified_partner": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "license_held": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service_sections"].queryset = ServiceSection.objects.order_by("sort_order", "name")
        self.fields["categories"].queryset = ServiceCategory.objects.order_by("name")
        self.fields["car_brands"].queryset = CarBrand.objects.order_by("-is_popular", "sort_order", "name")


class StationBrandsForm(forms.ModelForm):
    class Meta:
        model = ServiceStation
        fields = ("car_brands",)
        widgets = {
            "car_brands": forms.SelectMultiple(
                attrs={"class": "form-select", "size": "12"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["car_brands"].queryset = CarBrand.objects.order_by(
            "-is_popular", "sort_order", "name"
        )


class StationOwnerProfileForm(forms.ModelForm):
    """Редактирование карточки СТО / частного мастера для владельца."""

    class Meta:
        model = ServiceStation
        fields = (
            "name",
            "executor_kind",
            "address",
            "district",
            "address_public_mode",
            "description_short",
            "description",
            "work_schedule_text",
            "is_open_24_7",
            "has_parking",
            "service_sections",
            "categories",
            "car_brands",
            "car_brands_all",
            "contact_phone",
            "whatsapp_phone",
            "telegram_username",
            "website",
            "vk_url",
            "instagram_url",
            "inn",
            "ogrn",
            "amenity_wifi",
            "amenity_coffee",
            "amenity_cards",
            "amenity_tow",
            "amenity_legal",
            "tagline",
            "experience_years",
            "master_bio",
            "avatar",
            "certified_partner",
            "license_held",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "maxlength": "200"}),
            "executor_kind": forms.Select(attrs={"class": "form-select"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "district": forms.Select(attrs={"class": "form-select"}),
            "address_public_mode": forms.Select(attrs={"class": "form-select"}),
            "description_short": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "work_schedule_text": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "service_sections": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "categories": forms.SelectMultiple(attrs={"class": "form-select", "size": "10"}),
            "car_brands": forms.SelectMultiple(attrs={"class": "form-select", "size": "12"}),
            "car_brands_all": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+7…"}),
            "whatsapp_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+7…"}),
            "telegram_username": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "vk_url": forms.URLInput(attrs={"class": "form-control"}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control"}),
            "inn": forms.TextInput(attrs={"class": "form-control"}),
            "ogrn": forms.TextInput(attrs={"class": "form-control"}),
            "amenity_wifi": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "amenity_coffee": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "amenity_cards": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "amenity_tow": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "amenity_legal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "experience_years": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "master_bio": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "certified_partner": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "license_held": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_open_24_7": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "has_parking": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["district"].queryset = District.objects.order_by("city_label", "name")
        self.fields["district"].empty_label = "— не выбран —"
        self.fields["district"].help_text = (
            "Чтобы карточку было видно в каталоге при выборе города в шапке сайта, "
            "выберите район из списка (город должен совпадать с вашим городом на сайте)."
        )
        self.fields["categories"].queryset = ServiceCategory.objects.order_by("name")
        self.fields["service_sections"].queryset = ServiceSection.objects.order_by("sort_order", "name")
        self.fields["service_sections"].help_text = (
            "Можно выбрать разделы вместо точечных услуг: вы будете показываться в каталоге при выборе раздела."
        )
        self.fields["car_brands"].queryset = CarBrand.objects.order_by(
            "-is_popular", "sort_order", "name"
        )
        self.fields["car_brands_all"].label = "Все марки"
        self.fields["car_brands_all"].help_text = (
            "Включите, если работаете с любой маркой: вы будете в результатах при любом фильтре по марке в каталоге."
        )

    def clean_contact_phone(self):
        raw = self.cleaned_data.get("contact_phone")
        if not (raw or "").strip():
            return ""
        try:
            return normalize_to_e164(raw.strip())
        except PhoneValidationError as e:
            raise forms.ValidationError(str(e)) from e

    def clean_whatsapp_phone(self):
        raw = self.cleaned_data.get("whatsapp_phone")
        if not (raw or "").strip():
            return ""
        try:
            return normalize_to_e164(raw.strip())
        except PhoneValidationError as e:
            raise forms.ValidationError(str(e)) from e


class StationServiceOfferLineForm(forms.ModelForm):
    """Строка прайса; пустая extra-форма не требует цену и категорию."""

    class Meta:
        model = StationServiceOffer
        fields = ("category", "service_title", "price_from_rub", "note")
        widgets = {
            "category": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "service_title": forms.TextInput(
                attrs={"class": "form-control form-control-sm", "placeholder": "Необязательно"}
            ),
            "price_from_rub": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "min": "1", "step": "1"}
            ),
            "note": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = False
        self.fields["price_from_rub"].required = False
        self.fields["service_title"].required = False
        self.fields["note"].required = False

    def clean(self):
        cleaned = super().clean()
        cat = cleaned.get("category")
        price = cleaned.get("price_from_rub")
        title = (cleaned.get("service_title") or "").strip()
        note = (cleaned.get("note") or "").strip()
        empty = cat is None and price in (None, "") and not title and not note
        if empty:
            return cleaned
        if cat is None:
            self.add_error("category", "Выберите категорию услуги.")
        if price in (None, ""):
            self.add_error("price_from_rub", "Укажите цену «от», ₽.")
        elif int(price) < 1:
            self.add_error("price_from_rub", "Цена должна быть больше нуля.")
        return cleaned


class StationServiceOfferFormSetBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        station = self.instance

        deleted_pks: set[int] = set()
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data:
                continue
            if data.get("DELETE") and form.instance.pk:
                deleted_pks.add(form.instance.pk)

        seen: set[int] = set()
        for form in self.forms:
            data = form.cleaned_data
            if not data:
                continue
            if data.get("DELETE"):
                continue
            cat = data.get("category")
            title = (data.get("service_title") or "").strip()
            note = (data.get("note") or "").strip()
            price = data.get("price_from_rub")
            if cat is None and price in (None, "") and not title and not note:
                continue
            if cat is None:
                form.add_error("category", "Выберите категорию или удалите неполную строку.")
                continue
            cid = cat.pk
            if cid in seen:
                form.add_error(
                    "category",
                    "Эта категория уже выбрана в другой строке — оставьте одну строку на категорию.",
                )
                continue
            seen.add(cid)

            # Новая строка без pk: конфликт с уникальным (station, category), если в БД уже есть
            # строка с этой категорией, и она не удаляется и не «убирается» сменой категории в форме.
            if not form.instance.pk:
                qs = StationServiceOffer.objects.filter(
                    station_id=station.pk,
                    category_id=cid,
                ).exclude(pk__in=deleted_pks)
                blocks = [
                    obj.pk
                    for obj in qs
                    if not self._form_updates_away_from_category(obj.pk, cid)
                ]
                if blocks:
                    form.add_error(
                        "category",
                        "Эта категория уже есть в прайсе. Измените существующую строку выше "
                        "или отметьте её «удалить», затем добавьте новую.",
                    )

    def _form_updates_away_from_category(self, offer_pk: int, category_id: int) -> bool:
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE"):
                continue
            if form.instance.pk != offer_pk:
                continue
            new_cat = data.get("category")
            new_id = new_cat.pk if new_cat else None
            old_id = form.instance.category_id
            return old_id == category_id and new_id != category_id
        return False


StationServiceOfferFormSet = inlineformset_factory(
    ServiceStation,
    StationServiceOffer,
    form=StationServiceOfferLineForm,
    formset=StationServiceOfferFormSetBase,
    extra=1,
    can_delete=True,
    max_num=40,
)
