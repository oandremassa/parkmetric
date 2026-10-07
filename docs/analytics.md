# Analytics definitions

All metrics are computed from persisted database operations. Current capacity is deliberately separate from historical measures.

## Current occupancy

For active spot records of a parking lot:

- total = all active spots;
- occupied = active spots with `status=occupied`;
- blocked = active spots with `status=blocked`;
- available = active spots with `status=free`;
- occupancy percentage = `occupied / total × 100` (0 when total is zero).

## Historical period

User-entered `start` and `end` dates are inclusive local calendar dates in each parking lot's IANA time zone. They are converted to a half-open UTC interval `[local start 00:00, day after local end 00:00)`.

A single parser applies a maximum five-year window and is reused by pages, API reports, and CSV exports.

## Metric dates and denominators

- **Entries**: stay `entered_at` falls in the period.
- **Exits**: closed stay `exited_at` falls in the period.
- **Simulated revenue**: successful simulated payment `created_at` falls in the period. Waivers contribute no revenue.
- **Average ticket**: arithmetic mean of successful payments with amount > 0. Denominator is shown in the UI/API.
- **Average stay**: arithmetic mean of elapsed durations for stays whose `exited_at` falls in the period. Denominator is the number of completed stays used.
- **Hourly distribution**: entry timestamp converted to local site time, grouped by local hour.
- **Daily series**: local day groups for entry, exit, and successful payment activity.
- **Monthly/annual series**: local calendar aggregation for the same events.

## Site comparison and currencies

Comparison rows preserve each parking lot's currency. ParkMetric never adds EUR, USD, or other currencies into a combined monetary total without conversion.
