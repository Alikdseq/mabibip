from django import forms


class StoOfferAcceptForm(forms.Form):
    """Явное действие пользователя — требование доказуемости согласия (152-ФЗ)."""

    accept_sto_offer = forms.BooleanField(
        label="Я принимаю условия лицензионного договора-оферты для СТО",
        required=True,
        error_messages={"required": "Необходимо принять условия оферты."},
    )
