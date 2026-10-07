from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from auditlog.models import AuditEvent
from billing.models import Payment
from parking.models import ParkingSpot, Stay
from parking.services import OperationConflict, close_stay, enter_vehicle, quote_stay
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class OperationTests(TestCase):
    def setUp(self):
        self.operator = make_user()
        self.lot = make_lot()
        grant(self.operator, self.lot)
        self.spot = make_spot(self.lot)
        self.vehicle = make_vehicle(self.operator)
        self.tariff = make_tariff(self.lot, self.operator, grace=10, interval=60, price="3.00", cap="10.00")

    def test_entry_assigns_spot_and_preserves_tariff_snapshot(self):
        entered = timezone.now()
        result = enter_vehicle(
            actor=self.operator,
            parking_lot=self.lot,
            vehicle=self.vehicle,
            entered_at=entered,
            idempotency_key="entry-1",
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        self.spot.refresh_from_db()
        self.assertEqual(stay.tariff_id, self.tariff.pk)
        self.assertEqual(stay.vehicle_plate_snapshot, self.vehicle.plate)
        self.assertEqual(stay.spot_code_snapshot, self.spot.code)
        self.assertEqual(stay.parking_lot_code_snapshot, self.lot.code)
        self.assertEqual(self.spot.status, ParkingSpot.Status.OCCUPIED)
        self.assertTrue(AuditEvent.objects.filter(event_type="stay.entered", object_id=str(stay.pk)).exists())

    def test_vehicle_cannot_have_two_active_stays_in_same_lot(self):
        make_spot(self.lot, "A-02")
        enter_vehicle(actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="a")
        with self.assertRaises(OperationConflict):
            enter_vehicle(actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="b")

    def test_failed_payment_keeps_stay_and_spot_active(self):
        entered = timezone.now() - timedelta(hours=2)
        result = enter_vehicle(
            actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="in"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = timezone.now()
        quote = quote_stay(stay, at=confirmed)
        response = close_stay(
            actor=self.operator,
            stay=stay,
            accepted_amount=quote["amount"],
            simulator_outcome="failure",
            confirmed_at=confirmed,
            idempotency_key="out-fail",
        )
        stay.refresh_from_db()
        self.spot.refresh_from_db()
        self.assertFalse(response["closed"])
        self.assertEqual(stay.status, Stay.Status.ACTIVE)
        self.assertIsNone(stay.exited_at)
        self.assertEqual(self.spot.status, ParkingSpot.Status.OCCUPIED)
        self.assertEqual(Payment.objects.filter(stay=stay, status=Payment.Status.FAILED).count(), 1)

    def test_successful_payment_closes_stay_atomically(self):
        entered = timezone.now() - timedelta(hours=2)
        result = enter_vehicle(
            actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="in"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = timezone.now()
        quote = quote_stay(stay, at=confirmed)
        response = close_stay(
            actor=self.operator,
            stay=stay,
            accepted_amount=quote["amount"],
            simulator_outcome="success",
            confirmed_at=confirmed,
            idempotency_key="out-ok",
        )
        stay.refresh_from_db()
        self.spot.refresh_from_db()
        self.assertTrue(response["closed"])
        self.assertEqual(stay.status, Stay.Status.CLOSED)
        self.assertEqual(stay.final_amount, Decimal(quote["amount"]))
        self.assertEqual(self.spot.status, ParkingSpot.Status.FREE)
        self.assertEqual(Payment.objects.filter(stay=stay, status=Payment.Status.SUCCEEDED).count(), 1)

    def test_zero_charge_closes_with_waiver(self):
        entered = timezone.now()
        result = enter_vehicle(
            actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="in"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = entered + timedelta(minutes=5)
        response = close_stay(
            actor=self.operator,
            stay=stay,
            accepted_amount="0.00",
            simulator_outcome="success",
            confirmed_at=confirmed,
            idempotency_key="waive",
        )
        stay.refresh_from_db()
        self.assertTrue(response["closed"])
        self.assertEqual(stay.final_amount, Decimal("0.00"))
        self.assertTrue(stay.zero_charge_reason)
        self.assertEqual(Payment.objects.get(stay=stay).status, Payment.Status.WAIVED)

    def test_changed_final_amount_requires_new_acceptance(self):
        entered = timezone.now()
        result = enter_vehicle(
            actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="in"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        preview = quote_stay(stay, at=entered + timedelta(minutes=59))
        with self.assertRaises(OperationConflict):
            close_stay(
                actor=self.operator,
                stay=stay,
                accepted_amount=preview["amount"],
                simulator_outcome="success",
                confirmed_at=entered + timedelta(minutes=61),
                idempotency_key="changed",
            )
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ACTIVE)
        self.assertFalse(Payment.objects.filter(stay=stay).exists())

    def test_completed_stay_is_immutable(self):
        entered = timezone.now() - timedelta(hours=1)
        result = enter_vehicle(
            actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="in"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = timezone.now()
        quote = quote_stay(stay, at=confirmed)
        close_stay(
            actor=self.operator, stay=stay, accepted_amount=quote["amount"], confirmed_at=confirmed,
            simulator_outcome="success", idempotency_key="out"
        )
        stay.refresh_from_db()
        stay.final_amount = Decimal("0.01")
        with self.assertRaises(ValidationError):
            stay.save()

    def test_occupied_spot_cannot_be_blocked_or_deactivated(self):
        enter_vehicle(actor=self.operator, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="in")
        self.spot.refresh_from_db()
        self.spot.status = ParkingSpot.Status.BLOCKED
        with self.assertRaises(ValidationError):
            self.spot.full_clean()

class HistoricalIntegrityTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.lot = make_lot()
        grant(self.user, self.lot)
        self.spot = make_spot(self.lot)
        self.vehicle = make_vehicle(self.user, "LOCKED")
        make_tariff(self.lot, self.user)

    def test_parking_lot_timezone_cannot_change_after_history_exists(self):
        result = enter_vehicle(actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="history-entry")
        self.assertTrue(result["stay_id"])
        self.lot.timezone = "America/New_York"
        with self.assertRaises(ValidationError):
            self.lot.full_clean()

    def test_vehicle_identity_cannot_change_during_active_stay(self):
        enter_vehicle(actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="active-entry")
        self.vehicle.plate = "CHANGED"
        with self.assertRaises(ValidationError):
            self.vehicle.full_clean()

    def test_occupied_status_cannot_be_set_manually(self):
        other = make_spot(self.lot, "B-01")
        other.status = ParkingSpot.Status.OCCUPIED
        with self.assertRaises(ValidationError):
            other.full_clean()
