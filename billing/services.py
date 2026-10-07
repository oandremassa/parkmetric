from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auditlog.services import audit
from .models import TariffVersion


@transaction.atomic
def create_tariff_version(*, parking_lot, actor, name, grace_minutes, interval_minutes, interval_price, daily_cap, effective_from=None):
    if not actor.is_platform_admin and not actor.can_manage_unit(parking_lot.pk):
        raise PermissionError("You do not have permission to manage tariffs for this parking lot.")

    effective_from = effective_from or timezone.now()
    current = (
        TariffVersion.objects.select_for_update()
        .filter(parking_lot=parking_lot, is_active=True)
        .order_by("-version")
        .first()
    )
    next_version = 1
    if current:
        next_version = current.version + 1
        if effective_from <= current.effective_from:
            raise ValidationError("A new tariff must become effective after the current version.")
        current.is_active = False
        current.effective_to = effective_from
        current.save(update_fields=["is_active", "effective_to"])

    tariff = TariffVersion(
        parking_lot=parking_lot,
        version=next_version,
        name=name,
        grace_minutes=grace_minutes,
        interval_minutes=interval_minutes,
        interval_price=interval_price,
        daily_cap=daily_cap,
        effective_from=effective_from,
        is_active=True,
        created_by=actor,
    )
    tariff.full_clean()
    tariff.save()
    audit(
        actor=actor,
        parking_lot=parking_lot,
        event_type="tariff.version_created",
        obj=tariff,
        detail={
            "version": tariff.version,
            "grace_minutes": tariff.grace_minutes,
            "interval_minutes": tariff.interval_minutes,
            "interval_price": str(tariff.interval_price),
            "daily_cap": str(tariff.daily_cap),
        },
    )
    return tariff


def active_tariff(parking_lot, at):
    tariff = (
        TariffVersion.objects.filter(
            parking_lot=parking_lot,
            effective_from__lte=at,
        )
        .filter(effective_to__isnull=True)
        .order_by("-version")
        .first()
    )
    if tariff:
        return tariff
    return (
        TariffVersion.objects.filter(
            parking_lot=parking_lot,
            effective_from__lte=at,
            effective_to__gt=at,
        )
        .order_by("-version")
        .first()
    )
