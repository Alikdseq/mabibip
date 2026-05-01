from django import forms
from django.core.exceptions import ValidationError

from apps.reviews.constants import REVIEW_PHOTO_MAX_BYTES
from apps.reviews.models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "text", "photo")
        widgets = {
            "rating": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 5}),
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "photo": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].label = "Фото (по желанию)"
        self.fields["photo"].required = False

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        if not f:
            return f
        if getattr(f, "size", 0) > REVIEW_PHOTO_MAX_BYTES:
            raise ValidationError(
                f"Файл слишком большой (максимум {REVIEW_PHOTO_MAX_BYTES // (1024 * 1024)} МБ)."
            )
        return f

    def clean(self):
        data = super().clean()
        rating = data.get("rating")
        text = (data.get("text") or "").strip()
        if rating is not None and int(rating) <= 3 and not text:
            raise forms.ValidationError(
                "При оценке 1–3 звезды укажите комментарий: что пошло не так."
            )
        return data
