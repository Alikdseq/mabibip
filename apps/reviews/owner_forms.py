"""Формы кабинета СТО для отзывов."""

from django import forms


class OwnerReviewReplyForm(forms.Form):
    text = forms.CharField(
        label="Ответ (публикуется под отзывом на странице станции)",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
    )


class OwnerReviewComplaintForm(forms.Form):
    reason = forms.CharField(
        label="Почему считаете отзыв недопустимым",
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
