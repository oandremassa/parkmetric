from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ParkingAccess

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("ParkMetric", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("ParkMetric", {"fields": ("role",)}),)
    list_display = ("username", "email", "role", "is_active", "is_staff")

@admin.register(ParkingAccess)
class ParkingAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "parking_lot", "is_active", "created_at")
    list_filter = ("is_active", "parking_lot")
