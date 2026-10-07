from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        OPERATOR = "operator", "Operator"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OPERATOR)

    @property
    def is_platform_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    def can_manage_unit(self, parking_lot_id):
        if not self.is_active:
            return False
        if self.is_platform_admin:
            return True
        if self.role != self.Role.MANAGER:
            return False
        return self.parking_accesses.filter(parking_lot_id=parking_lot_id, is_active=True).exists()

    def can_operate_unit(self, parking_lot_id):
        if not self.is_active:
            return False
        if self.is_platform_admin:
            return True
        return self.parking_accesses.filter(parking_lot_id=parking_lot_id, is_active=True).exists()


class ParkingAccess(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="parking_accesses")
    parking_lot = models.ForeignKey("parking.ParkingLot", on_delete=models.CASCADE, related_name="user_accesses")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "parking_lot"], name="uniq_user_parking_access"),
        ]
        ordering = ["parking_lot__name", "user__username"]

    def __str__(self):
        return f"{self.user.username} → {self.parking_lot.code}"
