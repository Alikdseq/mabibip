from django import forms


class DriverProblemForm(forms.Form):
    title = forms.CharField(max_length=120, label="Кратко", widget=forms.TextInput(attrs={"class": "form-control"}))
    description = forms.CharField(
        label="Описание проблемы",
        max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
    car_brand = forms.CharField(required=False, max_length=80, label="Марка авто", widget=forms.TextInput(attrs={"class": "form-control"}))
    city_label = forms.CharField(required=False, max_length=120, label="Город", widget=forms.TextInput(attrs={"class": "form-control"}))
