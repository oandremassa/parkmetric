from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("Enter a valid IANA time zone, e.g. Europe/Berlin.") from exc


class ParkingLot(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=32, unique=True)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Berlin", validators=[validate_timezone])
    currency = models.CharField(max_length=3, default="EUR")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        self.currency = self.currency.upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError({"currency": "Use a three-letter ISO-style currency code."})
        if self.pk:
            original = ParkingLot.objects.filter(pk=self.pk).only("is_active", "timezone", "currency").first()
            has_stays = self.stays.exists()
            has_active_stays = self.stays.filter(status="active").exists()
            if original:
                errors = {}
                if has_active_stays and original.is_active and not self.is_active:
                    errors["is_active"] = "A parking lot with active stays cannot be deactivated."
                if has_stays and original.timezone != self.timezone:
                    errors["timezone"] = "Time zone cannot change after operational history exists."
                if has_stays and original.currency != self.currency:
                    errors["currency"] = "Currency cannot change after operational history exists."
                if errors:
                    raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ParkingSpot(models.Model):
    class Status(models.TextChoices):
        FREE = "free", "Free"
        OCCUPIED = "occupied", "Occupied"
        BLOCKED = "blocked", "Blocked"

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.PROTECT, related_name="spots")
    code = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.FREE)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["parking_lot__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["parking_lot", "code"], name="uniq_spot_code_per_lot"),
        ]

    def clean(self):
        original = None
        if self.pk:
            original = ParkingSpot.objects.filter(pk=self.pk).only(
                "status", "is_active", "parking_lot_id", "code"
            ).first()
        if self.status == self.Status.OCCUPIED and (not original or original.status != self.Status.OCCUPIED):
            raise ValidationError({"status": "Occupied status is controlled by active stays and cannot be set manually."})
        if original and original.status == self.Status.OCCUPIED:
            errors = {}
            if self.status != self.Status.OCCUPIED:
                errors["status"] = "An occupied spot cannot change status manually."
            if not self.is_active:
                errors["is_active"] = "An occupied spot cannot be deactivated."
            if original.parking_lot_id != self.parking_lot_id:
                errors["parking_lot"] = "An occupied spot cannot move to another parking lot."
            if original.code != self.code:
                errors["code"] = "An occupied spot code cannot change."
            if errors:
                raise ValidationError(errors)

    @property
    def is_operational(self):
        return self.is_active and self.status == self.Status.FREE

    def __str__(self):
        return f"{self.parking_lot.code}/{self.code}"


class Vehicle(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_vehicles", null=True, blank=True
    )
    plate = models.CharField(max_length=24)
    country = models.CharField(max_length=3, default="DE")
    make = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=64, blank=True)
    color = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plate"]
        constraints = [
            models.UniqueConstraint(fields=["plate", "country"], name="uniq_vehicle_plate_country"),
        ]

    def _normalize_identity(self):
        self.plate = "".join(self.plate.upper().split())
        self.country = self.country.upper()

    def clean(self):
        self._normalize_identity()
        if self.pk:
            original = Vehicle.objects.filter(pk=self.pk).only("plate", "country", "is_active").first()
            has_active_stays = self.stays.filter(status="active").exists()
            if original and has_active_stays:
                errors = {}
                if original.plate != self.plate:
                    errors["plate"] = "Plate cannot change while the vehicle has an active stay."
                if original.country != self.country:
                    errors["country"] = "Country cannot change while the vehicle has an active stay."
                if original.is_active and not self.is_active:
                    errors["is_active"] = "A vehicle with an active stay cannot be deactivated."
                if errors:
                    raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._normalize_identity()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.plate} ({self.country})"


class Stay(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    parking_lot = models.ForeignKey(ParkingLot, on_delete=models.PROTECT, related_name="stays")
    spot = models.ForeignKey(ParkingSpot, on_delete=models.PROTECT, related_name="stays")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="stays")
    tariff = models.ForeignKey("billing.TariffVersion", on_delete=models.PROTECT, related_name="stays")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    entered_at = models.DateTimeField(default=timezone.now)
    exited_at = models.DateTimeField(null=True, blank=True)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3)
    zero_charge_reason = models.CharField(max_length=120, blank=True)
    vehicle_plate_snapshot = models.CharField(max_length=24)
    spot_code_snapshot = models.CharField(max_length=32)
    parking_lot_code_snapshot = models.CharField(max_length=32)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_stays")
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="closed_stays", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["spot"], condition=Q(status="active"), name="uniq_active_stay_per_spot"
            ),
            models.UniqueConstraint(
                fields=["parking_lot", "vehicle"],
                condition=Q(status="active"),
                name="uniq_active_vehicle_per_lot",
            ),
            models.CheckConstraint(
                condition=Q(exited_at__isnull=True) | Q(exited_at__gte=models.F("entered_at")),
                name="stay_exit_not_before_entry",
            ),
            models.CheckConstraint(
                condition=(Q(status="active", exited_at__isnull=True) | Q(status="closed", exited_at__isnull=False)),
                name="stay_status_exit_consistency",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = Stay.objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.CLOSED:
                immutable = [
                    "parking_lot_id", "spot_id", "vehicle_id", "tariff_id", "status", "entered_at",
                    "exited_at", "final_amount", "currency", "zero_charge_reason",
                    "vehicle_plate_snapshot", "spot_code_snapshot", "parking_lot_code_snapshot",
                    "created_by_id", "closed_by_id",
                ]
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("Completed stays are immutable.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Stay #{self.pk} {self.vehicle_plate_snapshot or self.vehicle} @ {self.parking_lot_code_snapshot or self.parking_lot.code}"
