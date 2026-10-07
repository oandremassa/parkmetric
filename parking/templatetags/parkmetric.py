from zoneinfo import ZoneInfo
from django import template

register = template.Library()

@register.filter
def lot_datetime(value, timezone_name):
    if not value:
        return "—"
    try:
        local = value.astimezone(ZoneInfo(timezone_name))
        return local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value.isoformat()

@register.filter
def duration_minutes(seconds):
    try:
        return round(int(seconds) / 60)
    except (TypeError, ValueError):
        return 0
