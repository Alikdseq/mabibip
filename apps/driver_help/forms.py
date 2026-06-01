from django import forms


class HelpRequestForm(forms.Form):
    message = forms.CharField(
        label="Что случилось",
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Застрял, не заводится, нужен выезд…"}),
    )
