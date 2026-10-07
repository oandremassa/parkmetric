from datetime import date
from django.test import SimpleTestCase

from analyticsapp.filters import PeriodError, parse_period


class PeriodFilterTests(SimpleTestCase):
    def test_default_is_thirty_inclusive_days(self):
        start, end = parse_period(today=date(2026, 10, 7))
        self.assertEqual(start.isoformat(), "2026-09-08")
        self.assertEqual(end.isoformat(), "2026-10-07")

    def test_start_after_end_is_rejected(self):
        with self.assertRaises(PeriodError):
            parse_period("2026-10-08", "2026-10-07")

    def test_range_limit_is_enforced(self):
        with self.assertRaises(PeriodError):
            parse_period("2020-01-01", "2026-10-07")
