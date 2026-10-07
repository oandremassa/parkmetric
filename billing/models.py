from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TariffVersion(models.Model):
    parking_lot = models.ForeignKey("parking.ParkingLot", on_delete=models.PROTECT, related_name="tariffs")
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=80, default="Standard")
    grace_minutes = models.PositiveIntegerField(default=10)
    interval_minutes = models.PositiveIntegerField(default=60)
    interval_price = models.DecimalField(max_digits=10, decimal_places=2)
    daily_cap = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tariffs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["parking_lot", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["parking_lot", "version"], name="uniq_tariff_version_per_lot"),
            models.UniqueConstraint(
                fields=["parking_lot"], condition=Q(is_active=True), name="uniq_active_tariff_per_lot"
            ),
            models.CheckConstraint(condition=Q(interval_minutes__gt=0), name="tariff_interval_positive"),
            models.CheckConstraint(condition=Q(interval_price__gte=0), name="tariff_price_nonnegative"),
            models.CheckConstraint(condition=Q(daily_cap__gte=0), name="tariff_cap_nonnegative"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gt=models.F("effective_from")),
                name="tariff_effective_range_valid",
            ),
        ]

    def clean(self):
        if self.interval_minutes <= 0:
            raise ValidationError({"interval_minutes": "Interval must be greater than zero."})
        if self.daily_cap < Decimal("0.00"):
            raise ValidationError({"daily_cap": "Daily cap cannot be negative."})

    def __str__(self):
        return f"{self.parking_lot.code} v{self.version} - {self.name}"


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        WAIVED = "waived", "Waived"

    stay = models.ForeignKey("parking.Stay", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices)
    simulated = models.BooleanField(default=True)
    simulator_reason = models.CharField(max_length=120, blank=True)
    receipt_reference = models.CharField(max_length=48, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["stay"],
                condition=Q(status__in=["succeeded", "waived"]),
                name="uniq_successful_payment_per_stay",
            ),
            models.CheckConstraint(condition=Q(amount__gte=0), name="payment_amount_nonnegative"),
        ]

    def __str__(self):
        return f"{self.receipt_reference} {self.status} {self.amount} {self.currency}"
