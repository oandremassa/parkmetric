# Pricing policy

## Inputs

Every tariff version stores:

- grace/tolerance minutes;
- interval length in minutes;
- price per interval;
- cap for each elapsed 24-hour window;
- effective start/end;
- version number.

A stay references the exact tariff version valid when it begins.

## Algorithm

1. Convert entry and confirmation instants to UTC and calculate true elapsed duration.
2. Reject a confirmation before entry.
3. If duration is less than or equal to the grace period, amount is `0.00`.
4. If grace is exceeded, charge the entire duration; the grace period is not subtracted.
5. Split elapsed duration into consecutive windows of at most 24 hours.
6. For each window, round started intervals upward:

   `intervals = ceil(window_seconds / interval_seconds)`

7. Calculate `raw = intervals × interval_price`.
8. Charge `min(raw, daily_cap)` for that window, including the final incomplete 24-hour window.
9. Sum window charges and quantize monetary output to cents using `Decimal`.

## Examples

Assume 10-minute grace, 60-minute interval, EUR 3.00 per interval, EUR 10.00 cap.

| Duration | Result | Reason |
|---|---:|---|
| 10 min | EUR 0.00 | At grace boundary |
| 11 min | EUR 3.00 | Grace exceeded; first started interval |
| 60 min | EUR 3.00 | One interval |
| 61 min | EUR 6.00 | Second interval started |
| 5 h | EUR 10.00 | Capped within first 24h window |
| 25 h | EUR 13.00 | EUR 10 first 24h + EUR 3 final 1h window |

## Quote acceptance

A displayed quote is an estimate at a specific timestamp. The checkout operation recalculates using the actual confirmation timestamp. If the recalculated amount differs from the amount the user accepted, the operation returns a conflict, keeps the stay active, and requires a new explicit confirmation.

## DST

Duration is based on elapsed UTC time rather than wall-clock subtraction. A stay crossing a daylight-saving transition therefore charges real elapsed time. Local time is used for presentation and report calendar boundaries.
