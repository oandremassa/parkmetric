import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditlog.services import (
    acquire_idempotency,
    audit,
    complete_idempotency,
)
from billing.models import Payment
from billing.pricing import calculate_charge
from billing.services import active_tariff
from .models import ParkingSpot, Stay, Vehicle


class OperationConflict(Exception):
    pass


def _require_operate(actor, lot_id):
    if not actor.is_active or not actor.can_operate_unit(lot_id):
        raise PermissionDenied("You do not have access to this parking lot.")


def _receipt_ref():
    return f"SIM-{uuid.uuid4().hex[:16].upper()}"


@transaction.atomic
def enter_vehicle(*, actor, parking_lot, vehicle, entered_at=None, spot_id=None, idempotency_key=None):
    _require_operate(actor, parking_lot.pk)
    if not parking_lot.is_active:
        raise ValidationError("This parking lot is inactive.")

    explicit_entered_at = entered_at
    entered_at = entered_at or timezone.now()
    payload = {
        "vehicle_id": vehicle.pk,
        "spot_id": spot_id,
    }
    if explicit_entered_at is not None:
        payload["entered_at"] = entered_at.isoformat()
    idem = None
    if idempotency_key:
        idem, existing = acquire_idempotency(
            key=idempotency_key,
            scope="stay.entry",
            actor=actor,
            parking_lot=parking_lot,
            payload=payload,
        )
        if existing:
            return existing.body

    vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
    if not vehicle.is_active:
        raise OperationConflict("This vehicle is inactive.")
    if Stay.objects.filter(parking_lot=parking_lot, vehicle=vehicle, status=Stay.Status.ACTIVE).exists():
        raise OperationConflict("This vehicle already has an active stay in this parking lot.")

    if spot_id:
        spot = (
            ParkingSpot.objects.select_for_update()
            .filter(pk=spot_id, parking_lot=parking_lot)
            .first()
        )
        if not spot:
            raise ValidationError("The selected spot does not belong to this parking lot.")
        if not spot.is_operational:
            raise OperationConflict("The selected spot is not available.")
    else:
        spot = (
            ParkingSpot.objects.select_for_update(skip_locked=True)
            .filter(parking_lot=parking_lot, is_active=True, status=ParkingSpot.Status.FREE)
            .order_by("code")
            .first()
        )
        if not spot:
            raise OperationConflict("No parking spots are currently available.")

    tariff = active_tariff(parking_lot, entered_at)
    if not tariff:
        raise OperationConflict("No valid tariff is configured for this parking lot.")

    try:
        stay = Stay.objects.create(
            parking_lot=parking_lot,
            spot=spot,
            vehicle=vehicle,
            tariff=tariff,
            entered_at=entered_at,
            currency=parking_lot.currency,
            vehicle_plate_snapshot=vehicle.plate,
            spot_code_snapshot=spot.code,
            parking_lot_code_snapshot=parking_lot.code,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise OperationConflict("The entry conflicts with another operation. Refresh and try again.") from exc

    spot.status = ParkingSpot.Status.OCCUPIED
    spot.save(update_fields=["status"])

    audit(
        actor=actor,
        parking_lot=parking_lot,
        event_type="stay.entered",
        obj=stay,
        detail={"vehicle": vehicle.plate, "spot": spot.code, "tariff_version": tariff.version},
    )
    body = {"stay_id": stay.pk, "status": stay.status, "spot": spot.code}
    if idem:
        complete_idempotency(idem, status_code=201, body=body)
    return body


def quote_stay(stay, at=None):
    if stay.status != Stay.Status.ACTIVE:
        raise OperationConflict("Only active stays can be quoted.")
    at = at or timezone.now()
    quote = calculate_charge(
        start=stay.entered_at,
        end=at,
        grace_minutes=stay.tariff.grace_minutes,
        interval_minutes=stay.tariff.interval_minutes,
        interval_price=stay.tariff.interval_price,
        daily_cap=stay.tariff.daily_cap,
    )
    result = quote.to_dict()
    result["currency"] = stay.currency
    result["quoted_at"] = at.isoformat()
    result["stay_id"] = stay.pk
    return result


@transaction.atomic
def close_stay(
    *,
    actor,
    stay,
    accepted_amount,
    simulator_outcome="success",
    confirmed_at=None,
    idempotency_key=None,
):
    stay = (
        Stay.objects.select_for_update()
        .select_related("parking_lot", "spot", "tariff", "vehicle")
        .get(pk=stay.pk)
    )
    parking_lot = stay.parking_lot
    _require_operate(actor, parking_lot.pk)

    explicit_confirmed_at = confirmed_at
    confirmed_at = confirmed_at or timezone.now()
    accepted_amount = Decimal(str(accepted_amount)).quantize(Decimal("0.01"))
    payload = {
        "stay_id": stay.pk,
        "accepted_amount": str(accepted_amount),
        "simulator_outcome": simulator_outcome,
    }
    if explicit_confirmed_at is not None:
        payload["confirmed_at"] = confirmed_at.isoformat()

    idem = None
    if idempotency_key:
        idem, existing = acquire_idempotency(
            key=idempotency_key,
            scope="stay.checkout",
            actor=actor,
            parking_lot=parking_lot,
            payload=payload,
        )
        if existing:
            return existing.body

    if stay.status != Stay.Status.ACTIVE:
        raise OperationConflict("This stay is already closed.")

    spot = ParkingSpot.objects.select_for_update().get(pk=stay.spot_id)
    quote = calculate_charge(
        start=stay.entered_at,
        end=confirmed_at,
        grace_minutes=stay.tariff.grace_minutes,
        interval_minutes=stay.tariff.interval_minutes,
        interval_price=stay.tariff.interval_price,
        daily_cap=stay.tariff.daily_cap,
    )

    if quote.amount != accepted_amount:
        raise OperationConflict(
            f"The final amount changed to {quote.amount} {stay.currency}. Refresh the quote before confirming."
        )

    if quote.amount == Decimal("0.00"):
        payment = Payment.objects.create(
            stay=stay,
            amount=Decimal("0.00"),
            currency=stay.currency,
            status=Payment.Status.WAIVED,
            simulated=True,
            simulator_reason="Within configured grace period",
            receipt_reference=_receipt_ref(),
            created_by=actor,
        )
        stay.zero_charge_reason = "Within configured grace period"
        event_type = "stay.waived_and_closed"
    elif simulator_outcome == "failure":
        payment = Payment.objects.create(
            stay=stay,
            amount=quote.amount,
            currency=stay.currency,
            status=Payment.Status.FAILED,
            simulated=True,
            simulator_reason="Controlled simulator failure",
            receipt_reference=_receipt_ref(),
            created_by=actor,
        )
        audit(
            actor=actor,
            parking_lot=parking_lot,
            event_type="payment.failed",
            obj=payment,
            detail={"stay_id": stay.pk, "amount": str(quote.amount), "currency": stay.currency},
        )
        body = {
            "stay_id": stay.pk,
            "closed": False,
            "payment_status": Payment.Status.FAILED,
            "amount": str(quote.amount),
            "currency": stay.currency,
            "receipt_reference": payment.receipt_reference,
        }
        if idem:
            complete_idempotency(idem, status_code=402, body=body)
        return body
    elif simulator_outcome == "success":
        payment = Payment.objects.create(
            stay=stay,
            amount=quote.amount,
            currency=stay.currency,
            status=Payment.Status.SUCCEEDED,
            simulated=True,
            simulator_reason="Controlled simulator success",
            receipt_reference=_receipt_ref(),
            created_by=actor,
        )
        event_type = "stay.paid_and_closed"
    else:
        raise ValidationError("simulator_outcome must be 'success' or 'failure'.")

    stay.status = Stay.Status.CLOSED
    stay.exited_at = confirmed_at
    stay.final_amount = quote.amount
    stay.closed_by = actor
    stay.save(update_fields=["status", "exited_at", "final_amount", "closed_by", "zero_charge_reason"])

    spot.status = ParkingSpot.Status.FREE
    spot.save(update_fields=["status"])

    audit(
        actor=actor,
        parking_lot=parking_lot,
        event_type=event_type,
        obj=stay,
        detail={
            "payment_id": payment.pk,
            "receipt_reference": payment.receipt_reference,
            "amount": str(quote.amount),
            "currency": stay.currency,
            "breakdown": quote.to_dict(),
        },
    )
    body = {
        "stay_id": stay.pk,
        "closed": True,
        "payment_status": payment.status,
        "amount": str(quote.amount),
        "currency": stay.currency,
        "receipt_reference": payment.receipt_reference,
    }
    if idem:
        complete_idempotency(idem, status_code=200, body=body)
    return body
