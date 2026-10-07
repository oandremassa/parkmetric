from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from billing.services import create_tariff_version
from parking.tests.factories import grant, make_lot, make_tariff, make_user


class TariffVersioningTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager", role="manager")
        self.lot = make_lot()
        grant(self.manager, self.lot)
        self.current = make_tariff(self.lot, self.manager, effective_from=timezone.now() - timedelta(days=2))

    def test_new_tariff_closes_previous_version(self):
        effective = timezone.now()
        new = create_tariff_version(
            parking_lot=self.lot,
            actor=self.manager,
            name="Updated",
            grace_minutes=15,
            interval_minutes=30,
            interval_price=Decimal("1.75"),
            daily_cap=Decimal("18.00"),
            effective_from=effective,
        )
        self.current.refresh_from_db()
        self.assertFalse(self.current.is_active)
        self.assertEqual(self.current.effective_to, effective)
        self.assertEqual(new.version, 2)
        self.assertTrue(new.is_active)

    def test_new_version_cannot_start_before_current(self):
        with self.assertRaises(ValidationError):
            create_tariff_version(
                parking_lot=self.lot,
                actor=self.manager,
                name="Bad",
                grace_minutes=10,
                interval_minutes=60,
                interval_price=Decimal("2.00"),
                daily_cap=Decimal("20.00"),
                effective_from=self.current.effective_from,
            )
