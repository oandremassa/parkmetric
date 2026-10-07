from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from auditlog.services import IdempotencyConflict
from billing.models import Payment
from parking.models import Stay
from parking.services import close_stay, enter_vehicle, quote_stay
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class IdempotencyTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.lot = make_lot()
        grant(self.user, self.lot)
        make_spot(self.lot)
        self.vehicle = make_vehicle(self.user)
        make_tariff(self.lot, self.user)

    def test_equivalent_entry_retry_returns_original_result(self):
        first = enter_vehicle(
            actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="same-entry"
        )
        second = enter_vehicle(
            actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="same-entry"
        )
        self.assertEqual(first, second)
        self.assertEqual(Stay.objects.count(), 1)

    def test_key_reuse_with_different_content_is_rejected(self):
        other = make_vehicle(self.user, "OTHER1")
        enter_vehicle(actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, idempotency_key="entry-key")
        with self.assertRaises(IdempotencyConflict):
            enter_vehicle(actor=self.user, parking_lot=self.lot, vehicle=other, idempotency_key="entry-key")

    def test_failed_payment_retry_same_key_does_not_duplicate_attempt(self):
        entered = timezone.now() - timedelta(hours=1)
        result = enter_vehicle(
            actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="entry"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = timezone.now()
        quote = quote_stay(stay, at=confirmed)
        first = close_stay(
            actor=self.user, stay=stay, accepted_amount=quote["amount"], simulator_outcome="failure",
            confirmed_at=confirmed, idempotency_key="failed-payment"
        )
        second = close_stay(
            actor=self.user, stay=stay, accepted_amount=quote["amount"], simulator_outcome="failure",
            confirmed_at=confirmed, idempotency_key="failed-payment"
        )
        self.assertEqual(first, second)
        self.assertEqual(Payment.objects.filter(stay=stay, status=Payment.Status.FAILED).count(), 1)

    def test_new_key_after_controlled_failure_can_retry(self):
        entered = timezone.now() - timedelta(hours=1)
        result = enter_vehicle(
            actor=self.user, parking_lot=self.lot, vehicle=self.vehicle, entered_at=entered, idempotency_key="entry"
        )
        stay = Stay.objects.get(pk=result["stay_id"])
        confirmed = timezone.now()
        quote = quote_stay(stay, at=confirmed)
        close_stay(
            actor=self.user, stay=stay, accepted_amount=quote["amount"], simulator_outcome="failure",
            confirmed_at=confirmed, idempotency_key="failed"
        )
        result = close_stay(
            actor=self.user, stay=stay, accepted_amount=quote["amount"], simulator_outcome="success",
            confirmed_at=confirmed, idempotency_key="retry-success"
        )
        self.assertTrue(result["closed"])
        self.assertEqual(Payment.objects.filter(stay=stay).count(), 2)
