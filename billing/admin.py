from django.contrib import admin
from .models import Payment, TariffVersion

@admin.register(TariffVersion)
class TariffVersionAdmin(admin.ModelAdmin):
    list_display = ("parking_lot", "version", "name", "effective_from", "effective_to", "is_active")
    readonly_fields = [f.name for f in TariffVersion._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_reference", "stay", "amount", "currency", "status", "created_at")
    readonly_fields = [f.name for f in Payment._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
