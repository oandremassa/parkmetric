
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from parking.models import Stay
from parking.services import enter_vehicle
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class PermissionTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager", role=User.Role.MANAGER)
        self.operator = make_user("operator", role=User.Role.OPERATOR)
        self.other_manager = make_user("other_manager", role=User.Role.MANAGER)
        self.lot_a = make_lot("lot-a", "Lot A")
        self.lot_b = make_lot("lot-b", "Lot B")
        grant(self.manager, self.lot_a)
        grant(self.operator, self.lot_a)
        grant(self.other_manager, self.lot_b)
        self.spot_a = make_spot(self.lot_a, "A-01")
        self.spot_b = make_spot(self.lot_b, "B-01")
        make_tariff(self.lot_a, self.manager)
        make_tariff(self.lot_b, self.other_manager)
        self.vehicle_a = make_vehicle(self.operator, "AAA1")
        self.vehicle_b = make_vehicle(self.other_manager, "BBB1")
        self.stay_b = Stay.objects.get(pk=enter_vehicle(
            actor=self.other_manager,
            parking_lot=self.lot_b,
            vehicle=self.vehicle_b,
            idempotency_key="b-entry",
        )["stay_id"])

    def test_manager_direct_url_to_other_unit_stay_returns_404(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("stay_detail", args=[self.stay_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_operator_cannot_open_spot_edit_url(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("spot_edit", args=[self.spot_a.pk]))
        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_open_audit_or_tariff_management(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("audit_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("tariff_list")).status_code, 403)

    def test_operator_cannot_export_reports(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("export_stays")).status_code, 403)
        self.assertEqual(self.client.get(reverse("export_payments")).status_code, 403)

    def test_operator_dashboard_does_not_expose_revenue(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("dashboard"), {"lot": self.lot_a.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Simulated revenue")
        self.assertContains(response, "Operational view")

    def test_vehicle_selector_does_not_expose_other_unit_vehicle(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("stay_entry"))
        self.assertContains(response, self.vehicle_a.plate)
        self.assertNotContains(response, self.vehicle_b.plate)

    def test_disabled_account_session_is_invalidated(self):
        self.client.force_login(self.operator)
        User.objects.filter(pk=self.operator.pk).update(is_active=False)
        response = self.client.get(reverse("stay_active"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_api_other_unit_object_is_not_retrievable(self):
        self.client.force_login(self.manager)
        response = self.client.get(f"/api/v1/stays/{self.stay_b.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_api_reports_reject_operator(self):
        self.client.force_login(self.operator)
        response = self.client.get("/api/v1/reports/summary/", {"parking_lot": self.lot_a.pk})
        self.assertEqual(response.status_code, 403)
