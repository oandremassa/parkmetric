from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.permissions import user_lot_ids
from parking.models import ParkingLot
from .filters import PeriodError, parse_period
from .services import (
    annual_series,
    compare_units,
    current_occupancy,
    daily_series,
    historical_metrics,
    hourly_entries,
    monthly_series,
)


@login_required
def dashboard(request):
    lot_ids = user_lot_ids(request.user)
    lots = ParkingLot.objects.filter(pk__in=lot_ids).order_by("name")
    selected_id = request.GET.get("lot")
    lot = lots.filter(pk=selected_id).first() if selected_id else lots.first()

    try:
        start_date, end_date = parse_period(request.GET.get("start"), request.GET.get("end"))
    except PeriodError as exc:
        messages.error(request, str(exc))
        start_date, end_date = parse_period()

    can_view_reports = request.user.is_platform_admin or request.user.role == request.user.Role.MANAGER
    context = {
        "lots": lots,
        "selected_lot": lot,
        "start_date": start_date,
        "end_date": end_date,
        "can_view_reports": can_view_reports,
    }
    if lot:
        context["occupancy"] = current_occupancy(lot)
    if lot and can_view_reports:
        context.update({
            "comparison": compare_units(lots, start_date, end_date),
            "metrics": historical_metrics(lot, start_date, end_date),
            "daily_series": daily_series(lot, start_date, end_date),
            "monthly_series": monthly_series(lot, start_date, end_date),
            "annual_series": annual_series(lot, start_date, end_date),
            "hourly": hourly_entries(lot, start_date, end_date),
        })
    return render(request, "analytics/dashboard.html", context)
