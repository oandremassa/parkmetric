from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, ParkingAccess


class UserCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "is_active")


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role", "is_active")


class ParkingAccessForm(forms.ModelForm):
    class Meta:
        model = ParkingAccess
        fields = ("parking_lot", "is_active")
