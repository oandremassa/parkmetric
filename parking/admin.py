from django.contrib import admin
from .models import ParkingLot, ParkingSpot, Stay, Vehicle

admin.site.register(ParkingLot)
admin.site.register(ParkingSpot)
admin.site.register(Vehicle)

@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = ("id", "parking_lot", "vehicle_plate_snapshot", "spot_code_snapshot", "status", "entered_at", "exited_at")
    readonly_fields = [f.name for f in Stay._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
