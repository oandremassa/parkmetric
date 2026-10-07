from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import ParkingAccess, User
from billing.models import TariffVersion
from parking.models import ParkingLot, ParkingSpot, Vehicle


def make_user(username="operator", role=User.Role.OPERATOR, active=True):
    user = User.objects.create_user(username=username, password="test-pass-123", role=role, is_active=active)
    return user


def make_lot(code="lot-a", name="Lot A", currency="EUR"):
    return ParkingLot.objects.create(name=name, code=code, timezone="Europe/Berlin", currency=currency)


def grant(user, lot):
    return ParkingAccess.objects.create(user=user, parking_lot=lot)


def make_spot(lot, code="A-01"):
    return ParkingSpot.objects.create(parking_lot=lot, code=code)


def make_vehicle(user, plate="TEST001"):
    return Vehicle.objects.create(created_by=user, plate=plate, country="DE")


def make_tariff(lot, user, *, grace=10, interval=60, price="2.50", cap="20.00", version=1, effective_from=None):
    return TariffVersion.objects.create(
        parking_lot=lot,
        version=version,
        name="Standard",
        grace_minutes=grace,
        interval_minutes=interval,
        interval_price=Decimal(price),
        daily_cap=Decimal(cap),
        effective_from=effective_from or (timezone.now() - timedelta(days=1)),
        is_active=True,
        created_by=user,
    )
