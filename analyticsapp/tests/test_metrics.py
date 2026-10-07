from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase

from analyticsapp.services import historical_metrics
from billing.models import Payment
from parking.models import Stay
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class MetricTests(TestCase):
    def setUp(self):
        self.user = make_user("manager", role="manager")
        self.lot = make_lot()
        grant(self.user, self.lot)
        self.tariff = make_tariff(self.lot, self.user)
        self.spots = [make_spot(self.lot, f"A-{i:02d}") for i in range(1, 4)]

    def _closed_stay(self, plate, entered, exited, amount, spot):
        vehicle = make_vehicle(self.user, plate)
        stay = Stay.objects.create(
            parking_lot=self.lot,
            spot=spot,
            vehicle=vehicle,
            tariff=self.tariff,
            status=Stay.Status.CLOSED,
            entered_at=entered,
            exited_at=exited,
            final_amount=Decimal(amount),
            currency="EUR",
            vehicle_plate_snapshot=vehicle.plate,
            spot_code_snapshot=spot.code,
            parking_lot_code_snapshot=self.lot.code,
            created_by=self.user,
            closed_by=self.user,
        )
        payment = Payment.objects.create(
            stay=stay,
            amount=Decimal(amount),
            currency="EUR",
            status=Payment.Status.SUCCEEDED,
            simulated=True,
            simulator_reason="test",
            receipt_reference=f"SIM-{plate}",
            created_by=self.user,
        )
        Payment.objects.filter(pk=payment.pk).update(created_at=exited)
        return stay

    def test_metrics_use_documented_timestamps_and_denominators(self):
        berlin = ZoneInfo("Europe/Berlin")
        day = date(2026, 6, 10)
        first_in = datetime.combine(day, time(8, 0), tzinfo=berlin).astimezone(dt_timezone.utc)
        second_in = datetime.combine(day, time(12, 0), tzinfo=berlin).astimezone(dt_timezone.utc)
        self._closed_stay("M1", first_in, first_in + timedelta(hours=1), "4.00", self.spots[0])
        self._closed_stay("M2", second_in, second_in + timedelta(hours=3), "8.00", self.spots[1])

        metrics = historical_metrics(self.lot, day, day)
        self.assertEqual(metrics["entries"], 2)
        self.assertEqual(metrics["exits"], 2)
        self.assertEqual(metrics["revenue"], Decimal("12.00"))
        self.assertEqual(metrics["avg_ticket"], Decimal("6.00"))
        self.assertEqual(metrics["avg_ticket_denominator"], 2)
        self.assertEqual(metrics["avg_stay_minutes"], 120.0)
        self.assertEqual(metrics["avg_stay_denominator"], 2)
