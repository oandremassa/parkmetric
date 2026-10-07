import math
import random
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import ParkingAccess, User
from auditlog.models import AuditEvent, IdempotencyRecord
from billing.models import Payment, TariffVersion
from billing.pricing import calculate_charge
from parking.models import ParkingLot, ParkingSpot, Stay, Vehicle


LOT_SPECS = [
    ("demo-central", "Central Station Garage", "Europe/Berlin", "EUR", 36, Decimal("2.80"), Decimal("24.00")),
    ("demo-river", "Riverside Parking", "Europe/Berlin", "EUR", 24, Decimal("2.20"), Decimal("18.00")),
    ("demo-airport", "Airport Long Stay", "Europe/Berlin", "EUR", 48, Decimal("3.40"), Decimal("28.00")),
]


class Command(BaseCommand):
    help = "Load deterministic synthetic demonstration data. Restricted to DEMO_MODE."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--reference-date", type=str, default=timezone.now().date().isoformat())
        parser.add_argument("--small", action="store_true", help="Load a compact 7-day demonstration instead of 90 days.")
        parser.add_argument("--reset", action="store_true", help="Remove prior demo data before loading.")
        parser.add_argument("--if-empty", action="store_true", help="Exit successfully without changes when demo data already exists.")

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("DEMO_MODE=true is required. Normal startup never loads or resets demo data.")
        if not settings.DEMO_PASSWORD:
            raise CommandError("DEMO_PASSWORD must be set explicitly for demonstration accounts.")
        if options["reset"] and not settings.ALLOW_DEMO_RESET:
            raise CommandError("ALLOW_DEMO_RESET=true is required to use --reset.")

        try:
            reference_date = datetime.fromisoformat(options["reference_date"]).date()
        except ValueError as exc:
            raise CommandError("--reference-date must use YYYY-MM-DD.") from exc

        if ParkingLot.objects.filter(code__startswith="demo-").exists() and not options["reset"]:
            if options["if_empty"]:
                self.stdout.write("Demo data already exists; no changes were made.")
                return
            raise CommandError("Demo data already exists. Re-run with --reset only in an explicitly enabled demo environment.")

        rng = random.Random(options["seed"])
        days = 7 if options["small"] else 90
        reference_dt = datetime.combine(reference_date, datetime.min.time(), tzinfo=dt_timezone.utc) + timedelta(hours=18)
        start_dt = reference_dt - timedelta(days=days)

        with transaction.atomic():
            if options["reset"]:
                self._reset_demo()

            admin = self._upsert_user("demo_admin", User.Role.ADMIN, settings.DEMO_PASSWORD, "Demo", "Administrator")
            manager = self._upsert_user("demo_manager", User.Role.MANAGER, settings.DEMO_PASSWORD, "Demo", "Manager")
            operator = self._upsert_user("demo_operator", User.Role.OPERATOR, settings.DEMO_PASSWORD, "Demo", "Operator")

            lots = []
            all_spots = {}
            tariffs = {}
            for index, (code, name, tz_name, currency, capacity, interval_price, cap) in enumerate(LOT_SPECS):
                lot, _ = ParkingLot.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "timezone": tz_name,
                        "currency": currency,
                        "address": f"Synthetic address {index + 1}",
                        "is_active": True,
                    },
                )
                lots.append(lot)
                ParkingAccess.objects.update_or_create(user=manager, parking_lot=lot, defaults={"is_active": True})
                ParkingAccess.objects.update_or_create(user=operator, parking_lot=lot, defaults={"is_active": True})

                spots = []
                for n in range(1, capacity + 1):
                    spot, _ = ParkingSpot.objects.update_or_create(
                        parking_lot=lot,
                        code=f"{chr(65 + (n - 1) // 12)}-{((n - 1) % 12) + 1:02d}",
                        defaults={"status": ParkingSpot.Status.FREE, "is_active": True},
                    )
                    spots.append(spot)
                # Reserve two operationally blocked spaces as a current-state example.
                for spot in spots[-2:]:
                    spot.status = ParkingSpot.Status.BLOCKED
                    spot.save(update_fields=["status"])
                all_spots[lot.pk] = spots[:-2]

                midpoint = start_dt + timedelta(days=days // 2)
                v1, _ = TariffVersion.objects.update_or_create(
                    parking_lot=lot,
                    version=1,
                    defaults={
                        "name": "Standard",
                        "grace_minutes": 10 + index * 5,
                        "interval_minutes": 60,
                        "interval_price": interval_price,
                        "daily_cap": cap,
                        "effective_from": start_dt - timedelta(days=30),
                        "effective_to": midpoint,
                        "is_active": False,
                        "created_by": admin,
                    },
                )
                v2, _ = TariffVersion.objects.update_or_create(
                    parking_lot=lot,
                    version=2,
                    defaults={
                        "name": "Standard",
                        "grace_minutes": 10 + index * 5,
                        "interval_minutes": 30 if index == 1 else 60,
                        "interval_price": interval_price + Decimal("0.30"),
                        "daily_cap": cap + Decimal("2.00"),
                        "effective_from": midpoint,
                        "effective_to": None,
                        "is_active": True,
                        "created_by": admin,
                    },
                )
                tariffs[lot.pk] = (v1, v2)

            vehicles = self._vehicles(rng, operator, count=140 if options["small"] else 320)
            created_stays = self._historical_stays(
                rng=rng,
                operator=operator,
                lots=lots,
                spots_by_lot=all_spots,
                tariffs=tariffs,
                vehicles=vehicles,
                start_dt=start_dt,
                reference_dt=reference_dt,
                days=days,
            )
            active_stays = self._active_stays(
                rng=rng,
                operator=operator,
                lots=lots,
                spots_by_lot=all_spots,
                tariffs=tariffs,
                vehicles=vehicles,
                reference_dt=reference_dt,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo loaded: {len(lots)} parking lots, {len(vehicles)} vehicles, "
            f"{created_stays} completed stays, {active_stays} active stays. "
            f"Reference date: {reference_date.isoformat()}, seed: {options['seed']}."
        ))
        self.stdout.write("Demo accounts: demo_admin, demo_manager, demo_operator. Password comes only from DEMO_PASSWORD.")

    def _upsert_user(self, username, role, password, first_name, last_name):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                "role": role,
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{username}@example.invalid",
                "is_active": True,
            },
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _vehicles(self, rng, creator, count):
        makes = [("Volkswagen", "Golf"), ("BMW", "3 Series"), ("Toyota", "Corolla"), ("Skoda", "Octavia"), ("Ford", "Focus")]
        colors = ["Black", "White", "Silver", "Blue", "Red"]
        vehicles = []
        for i in range(count):
            make, model = rng.choice(makes)
            vehicle, _ = Vehicle.objects.update_or_create(
                plate=f"DEMO{i:04d}",
                country="DE",
                defaults={"make": make, "model": model, "color": rng.choice(colors), "is_active": True, "created_by": creator},
            )
            vehicles.append(vehicle)
        return vehicles

    def _historical_stays(self, *, rng, operator, lots, spots_by_lot, tariffs, vehicles, start_dt, reference_dt, days):
        created = 0
        for lot_index, lot in enumerate(lots):
            spots = spots_by_lot[lot.pk]
            spot_available = {spot.pk: start_dt for spot in spots}
            vehicle_available = {vehicle.pk: start_dt for vehicle in vehicles}
            candidates = []
            for day_offset in range(days):
                day = start_dt + timedelta(days=day_offset)
                weekday_factor = 0.72 if day.weekday() >= 5 else 1.0
                wave = 1.0 + 0.28 * math.sin(day_offset / 6)
                base = (18 + lot_index * 5) * weekday_factor * wave
                count = max(4, int(base + rng.randint(-4, 5)))
                for _ in range(count):
                    hour = rng.choices(
                        population=[7, 8, 9, 11, 12, 13, 16, 17, 18, 20],
                        weights=[5, 12, 8, 5, 7, 5, 6, 13, 9, 3],
                        k=1,
                    )[0]
                    entry = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
                    if entry >= reference_dt - timedelta(hours=3):
                        continue
                    candidates.append(entry)
            candidates.sort()

            for entry in candidates:
                available_spots = [s for s in spots if spot_available[s.pk] <= entry]
                available_vehicles = [v for v in vehicles if vehicle_available[v.pk] <= entry]
                if not available_spots or not available_vehicles:
                    continue
                spot = rng.choice(available_spots)
                vehicle = rng.choice(available_vehicles)

                if rng.random() < 0.08:
                    duration_minutes = rng.randint(2, 9 + lot_index * 5)  # waiver examples
                elif rng.random() < 0.03:
                    duration_minutes = rng.randint(1500, 3100)  # multi-day examples
                else:
                    duration_minutes = max(15, int(rng.lognormvariate(4.45, 0.72)))
                exit_at = min(entry + timedelta(minutes=duration_minutes), reference_dt - timedelta(minutes=10))
                if exit_at <= entry:
                    continue

                spot_available[spot.pk] = exit_at
                vehicle_available[vehicle.pk] = exit_at
                v1, v2 = tariffs[lot.pk]
                tariff = v1 if entry < v2.effective_from else v2
                quote = calculate_charge(
                    start=entry,
                    end=exit_at,
                    grace_minutes=tariff.grace_minutes,
                    interval_minutes=tariff.interval_minutes,
                    interval_price=tariff.interval_price,
                    daily_cap=tariff.daily_cap,
                )
                stay = Stay.objects.create(
                    parking_lot=lot,
                    spot=spot,
                    vehicle=vehicle,
                    tariff=tariff,
                    status=Stay.Status.CLOSED,
                    entered_at=entry,
                    exited_at=exit_at,
                    final_amount=quote.amount,
                    currency=lot.currency,
                    zero_charge_reason="Within configured grace period" if quote.amount == Decimal("0.00") else "",
                    vehicle_plate_snapshot=vehicle.plate,
                    spot_code_snapshot=spot.code,
                    parking_lot_code_snapshot=lot.code,
                    created_by=operator,
                    closed_by=operator,
                )
                if quote.amount == Decimal("0.00"):
                    status = Payment.Status.WAIVED
                    Payment.objects.create(
                        stay=stay,
                        amount=Decimal("0.00"),
                        currency=lot.currency,
                        status=status,
                        simulated=True,
                        simulator_reason="Within configured grace period",
                        receipt_reference=f"SIM-DEMO-W-{stay.pk:08d}",
                        created_by=operator,
                    )
                else:
                    if rng.random() < 0.07:
                        failed = Payment.objects.create(
                            stay=stay,
                            amount=quote.amount,
                            currency=lot.currency,
                            status=Payment.Status.FAILED,
                            simulated=True,
                            simulator_reason="Controlled synthetic failure",
                            receipt_reference=f"SIM-DEMO-F-{stay.pk:08d}",
                            created_by=operator,
                        )
                        Payment.objects.filter(pk=failed.pk).update(created_at=exit_at - timedelta(minutes=1))
                    payment = Payment.objects.create(
                        stay=stay,
                        amount=quote.amount,
                        currency=lot.currency,
                        status=Payment.Status.SUCCEEDED,
                        simulated=True,
                        simulator_reason="Controlled synthetic success",
                        receipt_reference=f"SIM-DEMO-S-{stay.pk:08d}",
                        created_by=operator,
                    )
                    Payment.objects.filter(pk=payment.pk).update(created_at=exit_at)
                AuditEvent.objects.create(
                    actor=operator,
                    parking_lot=lot,
                    event_type="demo.stay_seeded",
                    object_type="Stay",
                    object_id=str(stay.pk),
                    detail={"synthetic": True, "amount": str(quote.amount), "tariff_version": tariff.version},
                )
                created += 1
        return created

    def _active_stays(self, *, rng, operator, lots, spots_by_lot, tariffs, vehicles, reference_dt):
        count = 0
        used_vehicles = set()
        for lot_index, lot in enumerate(lots):
            free_spots = [s for s in spots_by_lot[lot.pk] if s.status == ParkingSpot.Status.FREE]
            for spot in free_spots[: 3 + lot_index]:
                vehicle = next(v for v in vehicles if v.pk not in used_vehicles)
                used_vehicles.add(vehicle.pk)
                tariff = tariffs[lot.pk][1]
                entered_at = reference_dt - timedelta(minutes=rng.randint(20, 420))
                stay = Stay.objects.create(
                    parking_lot=lot,
                    spot=spot,
                    vehicle=vehicle,
                    tariff=tariff,
                    status=Stay.Status.ACTIVE,
                    entered_at=entered_at,
                    currency=lot.currency,
                    vehicle_plate_snapshot=vehicle.plate,
                    spot_code_snapshot=spot.code,
                    parking_lot_code_snapshot=lot.code,
                    created_by=operator,
                )
                spot.status = ParkingSpot.Status.OCCUPIED
                spot.save(update_fields=["status"])
                if count % 3 == 0:
                    quote = calculate_charge(
                        start=entered_at,
                        end=reference_dt,
                        grace_minutes=tariff.grace_minutes,
                        interval_minutes=tariff.interval_minutes,
                        interval_price=tariff.interval_price,
                        daily_cap=tariff.daily_cap,
                    )
                    if quote.amount > 0:
                        Payment.objects.create(
                            stay=stay,
                            amount=quote.amount,
                            currency=lot.currency,
                            status=Payment.Status.FAILED,
                            simulated=True,
                            simulator_reason="Controlled synthetic failure",
                            receipt_reference=f"SIM-DEMO-AF-{stay.pk:08d}",
                            created_by=operator,
                        )
                AuditEvent.objects.create(
                    actor=operator,
                    parking_lot=lot,
                    event_type="demo.active_stay_seeded",
                    object_type="Stay",
                    object_id=str(stay.pk),
                    detail={"synthetic": True},
                )
                count += 1
        return count

    def _reset_demo(self):
        demo_lots = ParkingLot.objects.filter(code__startswith="demo-")
        demo_stays = Stay.objects.filter(parking_lot__in=demo_lots)
        Payment.objects.filter(stay__in=demo_stays).delete()
        AuditEvent.objects.filter(parking_lot__in=demo_lots).delete()
        IdempotencyRecord.objects.filter(parking_lot__in=demo_lots).delete()
        demo_stays.delete()
        TariffVersion.objects.filter(parking_lot__in=demo_lots).delete()
        ParkingAccess.objects.filter(parking_lot__in=demo_lots).delete()
        ParkingSpot.objects.filter(parking_lot__in=demo_lots).delete()
        demo_lots.delete()
        Vehicle.objects.filter(plate__startswith="DEMO").delete()
        User.objects.filter(username__startswith="demo_").delete()
