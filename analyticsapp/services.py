from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Avg, Count, Sum
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth, TruncYear

from billing.models import Payment
from parking.models import ParkingSpot, Stay


def period_bounds(parking_lot, start_date, end_date):
    """Interpret inclusive calendar dates in the parking lot's local timezone and return UTC bounds [start, end)."""
    tz = ZoneInfo(parking_lot.timezone)
    start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)


def current_occupancy(parking_lot):
    spots = ParkingSpot.objects.filter(parking_lot=parking_lot, is_active=True)
    total = spots.count()
    occupied = spots.filter(status=ParkingSpot.Status.OCCUPIED).count()
    blocked = spots.filter(status=ParkingSpot.Status.BLOCKED).count()
    available = spots.filter(status=ParkingSpot.Status.FREE).count()
    percentage = (occupied / total * 100) if total else 0
    return {
        "total": total,
        "occupied": occupied,
        "blocked": blocked,
        "available": available,
        "occupancy_pct": round(percentage, 1),
    }


def historical_metrics(parking_lot, start_date, end_date):
    start, end = period_bounds(parking_lot, start_date, end_date)
    entries = Stay.objects.filter(parking_lot=parking_lot, entered_at__gte=start, entered_at__lt=end).count()
    exits_qs = Stay.objects.filter(
        parking_lot=parking_lot,
        status=Stay.Status.CLOSED,
        exited_at__gte=start,
        exited_at__lt=end,
    )
    exits = exits_qs.count()
    successful = Payment.objects.filter(
        stay__parking_lot=parking_lot,
        status__in=[Payment.Status.SUCCEEDED, Payment.Status.WAIVED],
        created_at__gte=start,
        created_at__lt=end,
    )
    revenue = successful.filter(status=Payment.Status.SUCCEEDED).aggregate(v=Sum("amount"))["v"] or Decimal("0.00")
    eligible_paid = successful.filter(status=Payment.Status.SUCCEEDED, amount__gt=0)
    avg_ticket = eligible_paid.aggregate(v=Avg("amount"))["v"] or Decimal("0.00")

    durations = []
    for entered_at, exited_at in exits_qs.values_list("entered_at", "exited_at"):
        if exited_at:
            durations.append((exited_at - entered_at).total_seconds())
    avg_stay_minutes = (sum(durations) / len(durations) / 60) if durations else 0

    return {
        "entries": entries,
        "exits": exits,
        "revenue": revenue,
        "currency": parking_lot.currency,
        "avg_ticket": avg_ticket,
        "avg_ticket_denominator": eligible_paid.count(),
        "avg_stay_minutes": round(avg_stay_minutes, 1),
        "avg_stay_denominator": len(durations),
    }


def daily_series(parking_lot, start_date, end_date):
    start, end = period_bounds(parking_lot, start_date, end_date)
    tz = ZoneInfo(parking_lot.timezone)
    entries = {
        row["day"]: row["count"]
        for row in (
            Stay.objects.filter(parking_lot=parking_lot, entered_at__gte=start, entered_at__lt=end)
            .annotate(day=TruncDate("entered_at", tzinfo=tz))
            .values("day")
            .annotate(count=Count("id"))
        )
    }
    exits = {
        row["day"]: row["count"]
        for row in (
            Stay.objects.filter(parking_lot=parking_lot, exited_at__gte=start, exited_at__lt=end)
            .annotate(day=TruncDate("exited_at", tzinfo=tz))
            .values("day")
            .annotate(count=Count("id"))
        )
    }
    payments = {
        row["day"]: row["amount"]
        for row in (
            Payment.objects.filter(
                stay__parking_lot=parking_lot,
                status=Payment.Status.SUCCEEDED,
                created_at__gte=start,
                created_at__lt=end,
            )
            .annotate(day=TruncDate("created_at", tzinfo=tz))
            .values("day")
            .annotate(amount=Sum("amount"))
        )
    }
    output = []
    cursor = start_date
    while cursor <= end_date:
        output.append({
            "day": cursor,
            "entries": entries.get(cursor, 0),
            "exits": exits.get(cursor, 0),
            "revenue": payments.get(cursor, Decimal("0.00")),
        })
        cursor += timedelta(days=1)
    return output


def hourly_entries(parking_lot, start_date, end_date):
    start, end = period_bounds(parking_lot, start_date, end_date)
    tz = ZoneInfo(parking_lot.timezone)
    rows = (
        Stay.objects.filter(parking_lot=parking_lot, entered_at__gte=start, entered_at__lt=end)
        .annotate(hour=ExtractHour("entered_at", tzinfo=tz))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    counts = {int(r["hour"]): r["count"] for r in rows}
    peak = max(counts, key=counts.get) if counts else None
    max_count = max(counts.values()) if counts else 0
    return [
        {
            "hour": h,
            "count": counts.get(h, 0),
            "is_peak": h == peak,
            "bar_pct": round((counts.get(h, 0) / max_count * 100), 1) if max_count else 0,
        }
        for h in range(24)
    ]


def compare_units(parking_lots, start_date, end_date):
    rows = []
    for lot in parking_lots:
        metrics = historical_metrics(lot, start_date, end_date)
        occupancy = current_occupancy(lot)
        rows.append({
            "lot": lot,
            **metrics,
            "occupancy_pct": occupancy["occupancy_pct"],
            "available": occupancy["available"],
        })
    return rows


def _periodic_series(parking_lot, start_date, end_date, truncator):
    start, end = period_bounds(parking_lot, start_date, end_date)
    tz = ZoneInfo(parking_lot.timezone)

    def grouped(qs, field, aggregate_name="count"):
        return qs.annotate(bucket=truncator(field, tzinfo=tz)).values("bucket").annotate(count=Count("id")).order_by("bucket")

    entries_rows = grouped(
        Stay.objects.filter(parking_lot=parking_lot, entered_at__gte=start, entered_at__lt=end),
        "entered_at",
    )
    exits_rows = grouped(
        Stay.objects.filter(parking_lot=parking_lot, exited_at__gte=start, exited_at__lt=end),
        "exited_at",
    )
    payment_rows = (
        Payment.objects.filter(
            stay__parking_lot=parking_lot,
            status=Payment.Status.SUCCEEDED,
            created_at__gte=start,
            created_at__lt=end,
        )
        .annotate(bucket=truncator("created_at", tzinfo=tz))
        .values("bucket")
        .annotate(amount=Sum("amount"))
        .order_by("bucket")
    )
    entries = {r["bucket"].date(): r["count"] for r in entries_rows}
    exits = {r["bucket"].date(): r["count"] for r in exits_rows}
    revenue = {r["bucket"].date(): r["amount"] for r in payment_rows}
    keys = sorted(set(entries) | set(exits) | set(revenue))
    return [
        {"bucket": key, "entries": entries.get(key, 0), "exits": exits.get(key, 0), "revenue": revenue.get(key, Decimal("0.00"))}
        for key in keys
    ]


def monthly_series(parking_lot, start_date, end_date):
    return _periodic_series(parking_lot, start_date, end_date, TruncMonth)


def annual_series(parking_lot, start_date, end_date):
    return _periodic_series(parking_lot, start_date, end_date, TruncYear)
