from datetime import date, timedelta

MAX_REPORT_DAYS = 1826  # inclusive range, roughly five years
DEFAULT_REPORT_DAYS = 30


class PeriodError(ValueError):
    pass


def parse_period(start_raw=None, end_raw=None, *, today=None):
    today = today or date.today()
    try:
        end_date = date.fromisoformat(end_raw) if end_raw else today
        start_date = date.fromisoformat(start_raw) if start_raw else end_date - timedelta(days=DEFAULT_REPORT_DAYS - 1)
    except ValueError as exc:
        raise PeriodError("Dates must use YYYY-MM-DD.") from exc
    if start_date > end_date:
        raise PeriodError("Start date cannot be after end date.")
    if (end_date - start_date).days + 1 > MAX_REPORT_DAYS:
        raise PeriodError(f"Date range cannot exceed {MAX_REPORT_DAYS} days.")
    return start_date, end_date
