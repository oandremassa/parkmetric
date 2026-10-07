import threading

from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from parking.models import ParkingLot, Stay, Vehicle
from parking.services import enter_vehicle
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class PostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = make_user()
        self.lot = make_lot()
        grant(self.user, self.lot)
        make_tariff(self.lot, self.user)

    def _run_threads(self, targets):
        barrier = threading.Barrier(len(targets))
        results = []
        lock = threading.Lock()

        def runner(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                value = fn()
                outcome = ("ok", value)
            except Exception as exc:
                outcome = ("error", exc)
            finally:
                close_old_connections()
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=runner, args=(fn,)) for fn in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertTrue(all(not t.is_alive() for t in threads), "Concurrency test thread timed out.")
        return results

    def test_two_entries_cannot_take_last_available_spot(self):
        make_spot(self.lot)
        v1 = make_vehicle(self.user, "ONE")
        v2 = make_vehicle(self.user, "TWO")
        entered = timezone.now()

        def action(vehicle_id, key):
            def fn():
                actor = User.objects.get(pk=self.user.pk)
                lot = ParkingLot.objects.get(pk=self.lot.pk)
                vehicle = Vehicle.objects.get(pk=vehicle_id)
                return enter_vehicle(
                    actor=actor, parking_lot=lot, vehicle=vehicle,
                    entered_at=entered, idempotency_key=key,
                )
            return fn

        results = self._run_threads([action(v1.pk, "k1"), action(v2.pk, "k2")])
        self.assertEqual(sum(1 for status, _ in results if status == "ok"), 1)
        self.assertEqual(Stay.objects.filter(status=Stay.Status.ACTIVE).count(), 1)

    def test_same_vehicle_concurrent_entry_is_not_duplicated(self):
        make_spot(self.lot, "A-01")
        make_spot(self.lot, "A-02")
        vehicle = make_vehicle(self.user, "SAME")
        entered = timezone.now()

        def action(key):
            def fn():
                return enter_vehicle(
                    actor=User.objects.get(pk=self.user.pk),
                    parking_lot=ParkingLot.objects.get(pk=self.lot.pk),
                    vehicle=Vehicle.objects.get(pk=vehicle.pk),
                    entered_at=entered,
                    idempotency_key=key,
                )
            return fn

        results = self._run_threads([action("a"), action("b")])
        self.assertEqual(sum(1 for status, _ in results if status == "ok"), 1)
        self.assertEqual(Stay.objects.filter(vehicle=vehicle, status=Stay.Status.ACTIVE).count(), 1)

    def test_same_idempotency_key_concurrently_returns_one_operation(self):
        make_spot(self.lot, "A-01")
        vehicle = make_vehicle(self.user, "IDEM")
        entered = timezone.now()

        def action():
            return enter_vehicle(
                actor=User.objects.get(pk=self.user.pk),
                parking_lot=ParkingLot.objects.get(pk=self.lot.pk),
                vehicle=Vehicle.objects.get(pk=vehicle.pk),
                entered_at=entered,
                idempotency_key="concurrent-idem",
            )

        results = self._run_threads([action, action])
        self.assertEqual(sum(1 for status, _ in results if status == "ok"), 2)
        stay_ids = {value["stay_id"] for status, value in results if status == "ok"}
        self.assertEqual(len(stay_ids), 1)
        self.assertEqual(Stay.objects.count(), 1)
