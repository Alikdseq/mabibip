import re

from django import forms

from apps.bookings.models import Booking, TimeSlot
from apps.bookings.slot_rules import slot_is_bookable

RU_PHONE_RE = re.compile(r"^\+?[0-9\-\s()]{10,18}$")


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("car_info", "contact_phone", "description")
        widgets = {
            "car_info": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "contact_phone": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "tel"},
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "autocomplete": "off"},
            ),
        }

    def __init__(
        self,
        *args,
        slot: TimeSlot | None = None,
        booking_user=None,
        **kwargs,
    ):
        self.slot = slot
        self._booking_user = booking_user
        super().__init__(*args, **kwargs)

    def clean_contact_phone(self):
        raw = self.cleaned_data["contact_phone"].strip()
        if not RU_PHONE_RE.match(raw):
            raise forms.ValidationError(
                "Укажите телефон в формате +7… или 8… (10–18 символов, цифры и пробелы)."
            )
        return raw

    def clean(self):
        data = super().clean()
        if self.slot and not slot_is_bookable(self.slot, for_user=self._booking_user):
            raise forms.ValidationError("Это окно уже занято или недоступно.")
        return data
