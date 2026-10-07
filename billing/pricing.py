from dataclasses import dataclass, asdict
from datetime import timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from math import ceil


MONEY = Decimal("0.01")
DAY_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class WindowCharge:
    window: int
    seconds: int
    intervals: int
    uncapped: Decimal
    charged: Decimal

    def to_dict(self):
        data = asdict(self)
        data["uncapped"] = str(self.uncapped)
        data["charged"] = str(self.charged)
        return data


@dataclass(frozen=True)
class ChargeQuote:
    amount: Decimal
    duration_seconds: int
    grace_applied: bool
    interval_minutes: int
    interval_price: Decimal
    daily_cap: Decimal
    windows: tuple

    def to_dict(self):
        return {
            "amount": str(self.amount),
            "duration_seconds": self.duration_seconds,
            "grace_applied": self.grace_applied,
            "interval_minutes": self.interval_minutes,
            "interval_price": str(self.interval_price),
            "daily_cap": str(self.daily_cap),
            "windows": [w.to_dict() for w in self.windows],
        }


def _elapsed_seconds(start, end):
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Pricing requires timezone-aware datetimes.")
    start_utc = start.astimezone(dt_timezone.utc)
    end_utc = end.astimezone(dt_timezone.utc)
    seconds = int((end_utc - start_utc).total_seconds())
    if seconds < 0:
        raise ValueError("Exit time cannot be earlier than entry time.")
    return seconds


def calculate_charge(*, start, end, grace_minutes, interval_minutes, interval_price, daily_cap):
    seconds = _elapsed_seconds(start, end)
    interval_price = Decimal(interval_price)
    daily_cap = Decimal(daily_cap)

    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be greater than zero.")
    if seconds <= grace_minutes * 60:
        return ChargeQuote(
            amount=Decimal("0.00"),
            duration_seconds=seconds,
            grace_applied=True,
            interval_minutes=interval_minutes,
            interval_price=interval_price,
            daily_cap=daily_cap,
            windows=tuple(),
        )

    remaining = seconds
    window_number = 1
    windows = []
    interval_seconds = interval_minutes * 60

    while remaining > 0:
        window_seconds = min(remaining, DAY_SECONDS)
        intervals = ceil(window_seconds / interval_seconds)
        uncapped = (interval_price * intervals).quantize(MONEY, rounding=ROUND_HALF_UP)
        charged = min(uncapped, daily_cap).quantize(MONEY, rounding=ROUND_HALF_UP)
        windows.append(WindowCharge(window_number, window_seconds, intervals, uncapped, charged))
        remaining -= window_seconds
        window_number += 1

    amount = sum((w.charged for w in windows), Decimal("0.00")).quantize(MONEY, rounding=ROUND_HALF_UP)
    return ChargeQuote(
        amount=amount,
        duration_seconds=seconds,
        grace_applied=False,
        interval_minutes=interval_minutes,
        interval_price=interval_price,
        daily_cap=daily_cap,
        windows=tuple(windows),
    )
