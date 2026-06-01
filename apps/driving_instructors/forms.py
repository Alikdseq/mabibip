from django import forms

from apps.driving_instructors.models import DrivingInstructorProfile, TransmissionType


class InstructorProfileForm(forms.ModelForm):
    class Meta:
        model = DrivingInstructorProfile
        fields = [
            "name",
            "city_label",
            "address",
            "description",
            "contact_phone",
            "transmission",
            "experience_years",
            "price_per_hour",
            "price_exam_package",
            "services_text",
            "is_published",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "city_label": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "transmission": forms.Select(attrs={"class": "form-select"}),
            "experience_years": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "price_per_hour": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "price_exam_package": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "services_text": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Город, площадка, экзамен, ночное вождение"}
            ),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
