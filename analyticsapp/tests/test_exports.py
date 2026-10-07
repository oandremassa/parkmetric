from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from analyticsapp.csvutils import safe_cell
from parking.models import Stay
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class CsvSafetyTests(TestCase):
    def test_formula_like_cells_are_escaped(self):
        for raw in ["=2+2", "+cmd", "-1+1", "@SUM(A1:A2)"]:
            self.assertTrue(safe_cell(raw).startswith("'"))

    def test_normal_text_is_unchanged(self):
        self.assertEqual(safe_cell("ABC123"), "ABC123")


class ExportAuthorizationTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager", role=User.Role.MANAGER)
        self.other = make_user("other", role=User.Role.MANAGER)
        self.lot_a = make_lot("a", "A")
        self.lot_b = make_lot("b", "B")
        grant(self.manager, self.lot_a)
        grant(self.other, self.lot_b)
        self.tariff_a = make_tariff(self.lot_a, self.manager)
        self.tariff_b = make_tariff(self.lot_b, self.other)
        self._stay(self.manager, self.lot_a, self.tariff_a, "=SAFE", "A1")
        self._stay(self.other, self.lot_b, self.tariff_b, "SECRET", "B1")

    def _stay(self, user, lot, tariff, plate, spot_code):
        spot = make_spot(lot, spot_code)
        vehicle = make_vehicle(user, plate)
        return Stay.objects.create(
            parking_lot=lot, spot=spot, vehicle=vehicle, tariff=tariff, status=Stay.Status.CLOSED,
            entered_at=tariff.effective_from, exited_at=tariff.effective_from,
            final_amount=Decimal("0.00"), currency=lot.currency, zero_charge_reason="test",
            vehicle_plate_snapshot=vehicle.plate, spot_code_snapshot=spot.code,
            parking_lot_code_snapshot=lot.code, created_by=user, closed_by=user,
        )

    def test_export_contains_all_authorized_rows_not_other_unit(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("export_stays"))
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("'=SAFE", content)
        self.assertNotIn("SECRET", content)
