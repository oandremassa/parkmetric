from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from parking.models import Stay
from parking.tests.factories import grant, make_lot, make_spot, make_tariff, make_user, make_vehicle


class ApiTests(TestCase):
    def setUp(self):
        self.operator = make_user("operator", role=User.Role.OPERATOR)
        self.manager = make_user("manager", role=User.Role.MANAGER)
        self.other = make_user("other", role=User.Role.OPERATOR)
        self.lot = make_lot("api-a", "API A")
        self.other_lot = make_lot("api-b", "API B")
        grant(self.operator, self.lot)
        grant(self.manager, self.lot)
        grant(self.other, self.other_lot)
        self.spot = make_spot(self.lot, "A-01")
        make_spot(self.other_lot, "B-01")
        make_tariff(self.lot, self.manager, price="3.00", cap="20.00")
        make_tariff(self.other_lot, self.other)
        self.vehicle = make_vehicle(self.operator, "API001")
        self.other_vehicle = make_vehicle(self.other, "SECRET1")

    def test_entry_requires_idempotency_key(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            "/api/v1/operations/entry/",
            {"parking_lot": self.lot.pk, "vehicle": self.vehicle.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_entry_and_checkout_flow(self):
        self.client.force_login(self.operator)
        entered = timezone.now()
        response = self.client.post(
            "/api/v1/operations/entry/",
            {"parking_lot": self.lot.pk, "vehicle": self.vehicle.pk},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="api-entry",
        )
        self.assertEqual(response.status_code, 201)
        stay_id = response.json()["stay_id"]
        stay = Stay.objects.get(pk=stay_id)
        # Move entry back in time to make a paid checkout deterministic for this isolated test.
        Stay.objects.filter(pk=stay.pk).update(entered_at=entered - timedelta(hours=2))
        quote = self.client.get(f"/api/v1/stays/{stay_id}/quote/")
        self.assertEqual(quote.status_code, 200)
        amount = quote.json()["amount"]
        checkout = self.client.post(
            f"/api/v1/stays/{stay_id}/checkout/",
            {"accepted_amount": amount, "simulator_outcome": "success"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="api-checkout",
        )
        self.assertEqual(checkout.status_code, 200)
        self.assertTrue(checkout.json()["closed"])

    def test_inaccessible_vehicle_identifier_is_rejected_without_entry(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            "/api/v1/operations/entry/",
            {"parking_lot": self.lot.pk, "vehicle": self.other_vehicle.pk},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="other-vehicle",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Stay.objects.filter(vehicle=self.other_vehicle, parking_lot=self.lot).exists())

    def test_spot_list_is_scoped_to_accessible_units(self):
        self.client.force_login(self.operator)
        response = self.client.get("/api/v1/spots/")
        ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(self.spot.pk, ids)
        self.assertNotIn(
            self.other_lot.spots.first().pk,
            ids,
        )

    def test_report_period_validation_is_consistent(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            "/api/v1/reports/summary/",
            {"parking_lot": self.lot.pk, "start": "2026-10-10", "end": "2026-10-01"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Start date cannot be after end date", str(response.json()))
