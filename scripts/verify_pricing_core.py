#!/usr/bin/env python3
"""Dependency-free verification of the core pricing module."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decimal import Decimal
from zoneinfo import ZoneInfo

from billing.pricing import calculate_charge


def quote(start, end, **overrides):
    args = {
        "start": start,
        "end": end,
        "grace_minutes": 10,
        "interval_minutes": 60,
        "interval_price": Decimal("3.00"),
        "daily_cap": Decimal("10.00"),
    }
    args.update(overrides)
    return calculate_charge(**args)


base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
assert quote(base, base + timedelta(minutes=10)).amount == Decimal("0.00")
assert quote(base, base + timedelta(minutes=11)).amount == Decimal("3.00")
assert quote(base, base + timedelta(minutes=61)).amount == Decimal("6.00")
assert quote(base, base + timedelta(hours=5)).amount == Decimal("10.00")
assert quote(base, base + timedelta(hours=25)).amount == Decimal("13.00")

berlin = ZoneInfo("Europe/Berlin")
spring_start = datetime(2026, 3, 29, 1, 30, tzinfo=berlin)
spring_end = datetime(2026, 3, 29, 3, 30, tzinfo=berlin)
assert quote(spring_start, spring_end, grace_minutes=0).duration_seconds == 3600

fall_start = datetime(2026, 10, 25, 1, 30, tzinfo=berlin)
fall_end = datetime(2026, 10, 25, 3, 30, tzinfo=berlin)
assert quote(fall_start, fall_end, grace_minutes=0).duration_seconds == 10800

try:
    quote(base, base - timedelta(seconds=1))
except ValueError:
    pass
else:
    raise AssertionError("Negative durations must be rejected")

print("pricing-core: PASS (grace, rounding, cap, multi-window, DST, negative duration)")
