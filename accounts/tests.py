from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from parking.tests.factories import grant, make_lot, make_user


class UserAdministrationPermissionTests(TestCase):
    def test_manager_cannot_access_user_administration(self):
        manager = make_user(username="manager", role=User.Role.MANAGER)
        grant(manager, make_lot())
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("user_list")).status_code, 403)

    def test_operator_cannot_toggle_access_directly(self):
        admin = make_user(username="admin", role=User.Role.ADMIN)
        target = make_user(username="target")
        access = grant(target, make_lot())
        operator = make_user(username="operator", role=User.Role.OPERATOR)
        self.client.force_login(operator)
        response = self.client.post(reverse("access_toggle", args=[access.pk]))
        self.assertEqual(response.status_code, 403)
        access.refresh_from_db()
        self.assertTrue(access.is_active)
