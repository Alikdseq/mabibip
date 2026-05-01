from __future__ import annotations

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(
        label="Сумма",
        min_value=Decimal("1.00"),
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    payout_details = forms.CharField(
        label="Реквизиты для выплаты",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Карта ****1234 / СБП / банк"}),
    )
    reason = forms.CharField(
        label="Комментарий",
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, max_amount: Decimal | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_amount = max_amount

    def clean_amount(self):
        v: Decimal = self.cleaned_data["amount"]
        if self._max_amount is not None and v > self._max_amount:
            raise ValidationError("Недостаточно доступных средств для вывода.")
        return v

