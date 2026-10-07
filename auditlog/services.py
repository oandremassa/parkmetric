import hashlib
import json
from dataclasses import dataclass
from django.db import IntegrityError, transaction
from .models import AuditEvent, IdempotencyRecord


class IdempotencyConflict(Exception):
    pass


@dataclass
class ExistingIdempotentResponse:
    status_code: int
    body: dict


def canonical_hash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit(*, actor, parking_lot, event_type, obj, detail=None):
    return AuditEvent.objects.create(
        actor=actor,
        parking_lot=parking_lot,
        event_type=event_type,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
        detail=detail or {},
    )


def acquire_idempotency(*, key, scope, actor, parking_lot, payload):
    request_hash = canonical_hash(payload)
    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                key=key,
                scope=scope,
                actor=actor,
                parking_lot=parking_lot,
                request_hash=request_hash,
            )
            return record, None
    except IntegrityError:
        record = (
            IdempotencyRecord.objects.select_for_update()
            .get(key=key, scope=scope, actor=actor, parking_lot=parking_lot)
        )
        if record.request_hash != request_hash:
            raise IdempotencyConflict("This idempotency key was already used with different request content.")
        if record.completed:
            return record, ExistingIdempotentResponse(record.response_code, record.response_body)
        # A concurrent transaction should normally have completed before this lock is acquired.
        # If it did not, reject safely rather than executing twice.
        raise IdempotencyConflict("An operation with this idempotency key is already in progress.")


def complete_idempotency(record, *, status_code, body):
    record.response_code = status_code
    record.response_body = body
    record.completed = True
    record.save(update_fields=["response_code", "response_body", "completed"])
