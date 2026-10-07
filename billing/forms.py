from django import forms


class TariffCreateForm(forms.Form):
    name = forms.CharField(max_length=80, initial="Standard")
    grace_minutes = forms.IntegerField(min_value=0, initial=10)
    interval_minutes = forms.IntegerField(min_value=1, initial=60)
    interval_price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    daily_cap = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
