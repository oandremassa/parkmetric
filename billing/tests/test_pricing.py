from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from billing.pricing import calculate_charge


class PricingTests(SimpleTestCase):
    def quote(self, start, end, **overrides):
        params = {
            "grace_minutes": 10,
            "interval_minutes": 60,
            "interval_price": Decimal("3.00"),
            "daily_cap": Decimal("10.00"),
        }
        params.update(overrides)
        return calculate_charge(start=start, end=end, **params)

    def test_exact_grace_boundary_is_zero(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        quote = self.quote(start, start + timedelta(minutes=10))
        self.assertEqual(quote.amount, Decimal("0.00"))
        self.assertTrue(quote.grace_applied)

    def test_once_grace_is_exceeded_total_time_is_charged(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        quote = self.quote(start, start + timedelta(minutes=10, seconds=1))
        self.assertEqual(quote.amount, Decimal("3.00"))
        self.assertEqual(quote.windows[0].intervals, 1)

    def test_started_interval_rounds_up(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        quote = self.quote(start, start + timedelta(minutes=60, seconds=1))
        self.assertEqual(quote.amount, Decimal("6.00"))
        self.assertEqual(quote.windows[0].intervals, 2)

    def test_each_elapsed_24h_window_has_its_own_cap(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        quote = self.quote(start, start + timedelta(hours=25))
        self.assertEqual(quote.amount, Decimal("13.00"))
        self.assertEqual(len(quote.windows), 2)
        self.assertEqual(quote.windows[0].charged, Decimal("10.00"))
        self.assertEqual(quote.windows[1].charged, Decimal("3.00"))

    def test_final_incomplete_window_is_capped_too(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        quote = self.quote(start, start + timedelta(hours=52))
        self.assertEqual(quote.amount, Decimal("30.00"))
        self.assertEqual([w.charged for w in quote.windows], [Decimal("10.00")] * 3)

    def test_spring_dst_uses_elapsed_time_not_wall_clock(self):
        berlin = ZoneInfo("Europe/Berlin")
        start = datetime(2026, 3, 29, 1, 30, tzinfo=berlin)
        end = datetime(2026, 3, 29, 3, 30, tzinfo=berlin)
        quote = self.quote(start, end, grace_minutes=0)
        self.assertEqual(quote.duration_seconds, 3600)
        self.assertEqual(quote.amount, Decimal("3.00"))

    def test_fall_dst_counts_repeated_hour(self):
        berlin = ZoneInfo("Europe/Berlin")
        start = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=0)
        end = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=1)
        quote = self.quote(start, end, grace_minutes=0)
        self.assertEqual(quote.duration_seconds, 3600)
        self.assertEqual(quote.amount, Decimal("3.00"))

    def test_negative_duration_is_rejected(self):
        start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            self.quote(start, start - timedelta(seconds=1))
