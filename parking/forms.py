import uuid
from django import forms
from .models import ParkingLot, ParkingSpot, Vehicle


class ParkingLotForm(forms.ModelForm):
    class Meta:
        model = ParkingLot
        fields = ("name", "code", "address", "timezone", "currency", "is_active")


class ParkingSpotForm(forms.ModelForm):
    class Meta:
        model = ParkingSpot
        fields = ("parking_lot", "code", "status", "is_active", "notes")

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.status == ParkingSpot.Status.OCCUPIED:
            if cleaned.get("status") == ParkingSpot.Status.BLOCKED or cleaned.get("is_active") is False:
                raise forms.ValidationError("An occupied spot cannot be blocked or deactivated.")
        return cleaned


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ("plate", "country", "make", "model", "color", "notes", "is_active")


class EntryForm(forms.Form):
    parking_lot = forms.ModelChoiceField(queryset=ParkingLot.objects.none())
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none())
    spot = forms.ModelChoiceField(queryset=ParkingSpot.objects.none(), required=False, help_text="Leave blank for automatic assignment.")
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.permissions import user_lot_ids
        lot_ids = user_lot_ids(user) if user else []
        self.fields["parking_lot"].queryset = ParkingLot.objects.filter(pk__in=lot_ids, is_active=True)
        vehicle_qs = Vehicle.objects.filter(is_active=True)
        if user and not user.is_platform_admin:
            from django.db.models import Q
            vehicle_qs = vehicle_qs.filter(Q(created_by=user) | Q(stays__parking_lot_id__in=lot_ids)).distinct()
        self.fields["vehicle"].queryset = vehicle_qs.order_by("plate")
        self.fields["spot"].queryset = ParkingSpot.objects.filter(
            parking_lot_id__in=lot_ids, is_active=True, status=ParkingSpot.Status.FREE
        ).select_related("parking_lot")
        if not self.initial.get("idempotency_key"):
            self.initial["idempotency_key"] = str(uuid.uuid4())

    def clean(self):
        cleaned = super().clean()
        lot = cleaned.get("parking_lot")
        spot = cleaned.get("spot")
        if lot and spot and spot.parking_lot_id != lot.pk:
            self.add_error("spot", "The selected spot belongs to another parking lot.")
        return cleaned


class CheckoutForm(forms.Form):
    accepted_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    simulator_outcome = forms.ChoiceField(choices=[("success", "Simulate success"), ("failure", "Simulate failure")])
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("idempotency_key"):
            self.initial["idempotency_key"] = str(uuid.uuid4())
