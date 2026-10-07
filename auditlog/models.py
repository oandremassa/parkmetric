from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_events")
    parking_lot = models.ForeignKey(
        "parking.ParkingLot", on_delete=models.PROTECT, related_name="audit_events", null=True, blank=True
    )
    event_type = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["parking_lot", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at} {self.event_type} {self.object_type}:{self.object_id}"


class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=128)
    scope = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    parking_lot = models.ForeignKey("parking.ParkingLot", on_delete=models.PROTECT)
    request_hash = models.CharField(max_length=64)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "actor", "parking_lot", "key"], name="uniq_idempotency_context"),
        ]
