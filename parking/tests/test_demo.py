from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from billing.models import Payment
from parking.models import ParkingLot, Stay


class DemoSeedTests(TestCase):
    def test_seed_is_disabled_outside_demo_mode(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--small", reference_date="2026-10-07")

    @override_settings(DEMO_MODE=True, ALLOW_DEMO_RESET=True, DEMO_PASSWORD="test-only-password")
    def test_small_demo_has_required_synthetic_cases_and_can_reset(self):
        output = StringIO()
        call_command(
            "seed_demo", "--small", "--seed", "21", "--reference-date", "2026-10-07", stdout=output
        )
        self.assertEqual(ParkingLot.objects.filter(code__startswith="demo-").count(), 3)
        self.assertTrue(Stay.objects.filter(status=Stay.Status.CLOSED).exists())
        self.assertTrue(Stay.objects.filter(status=Stay.Status.ACTIVE).exists())
        self.assertTrue(Payment.objects.filter(status=Payment.Status.FAILED).exists())
        self.assertTrue(Payment.objects.filter(status=Payment.Status.WAIVED).exists())
        counts_before = (
            Stay.objects.count(),
            Payment.objects.count(),
        )
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--small", "--seed", "21", "--reference-date", "2026-10-07")
        call_command(
            "seed_demo", "--small", "--if-empty", "--seed", "21", "--reference-date", "2026-10-07"
        )
        self.assertEqual(counts_before, (Stay.objects.count(), Payment.objects.count()))
        call_command(
            "seed_demo", "--small", "--reset", "--seed", "21", "--reference-date", "2026-10-07"
        )
        self.assertEqual(counts_before, (Stay.objects.count(), Payment.objects.count()))
