
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.permissions import admin_required, manager_or_admin_required, user_lot_ids
from analyticsapp.csvutils import streaming_csv
from analyticsapp.filters import PeriodError, parse_period
from analyticsapp.services import period_bounds
from auditlog.models import AuditEvent
from auditlog.services import IdempotencyConflict, audit
from billing.forms import TariffCreateForm
from billing.models import Payment, TariffVersion
from billing.services import create_tariff_version
from .forms import CheckoutForm, EntryForm, ParkingLotForm, ParkingSpotForm, VehicleForm
from .models import ParkingLot, ParkingSpot, Stay, Vehicle
from .services import OperationConflict, close_stay, enter_vehicle, quote_stay


def _lots_for(user):
    return ParkingLot.objects.filter(pk__in=user_lot_ids(user))


def _get_lot_for_user(user, pk):
    lot = get_object_or_404(ParkingLot, pk=pk)
    if lot.pk not in user_lot_ids(user):
        raise Http404
    return lot


def _paginate(request, qs, per_page=25):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


def _period_or_default(request):
    try:
        return parse_period(request.GET.get("start"), request.GET.get("end"))
    except PeriodError as exc:
        messages.error(request, str(exc))
        return parse_period()


def _filter_by_local_period(qs, lots, *, field, start_date, end_date, lot_lookup="parking_lot"):
    lots = list(lots)
    combined = Q(pk__in=[])
    for lot in lots:
        start_utc, end_utc = period_bounds(lot, start_date, end_date)
        clause = {
            f"{lot_lookup}_id": lot.pk,
            f"{field}__gte": start_utc,
            f"{field}__lt": end_utc,
        }
        combined |= Q(**clause)
    return qs.filter(combined)


@login_required
def lot_list(request):
    return render(request, "parking/lot_list.html", {"lots": _lots_for(request.user).order_by("name")})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def lot_create(request):
    form = ParkingLotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lot = form.save()
        audit(actor=request.user, parking_lot=lot, event_type="parking_lot.created", obj=lot)
        messages.success(request, "Parking lot created.")
        return redirect("lot_list")
    return render(request, "shared/form_page.html", {"form": form, "title": "Create parking lot", "submit_label": "Save"})


@login_required
@manager_or_admin_required
@require_http_methods(["GET", "POST"])
def lot_edit(request, pk):
    lot = _get_lot_for_user(request.user, pk)
    if not request.user.is_platform_admin:
        raise PermissionDenied
    form = ParkingLotForm(request.POST or None, instance=lot)
    if request.method == "POST" and form.is_valid():
        lot = form.save()
        audit(actor=request.user, parking_lot=lot, event_type="parking_lot.updated", obj=lot)
        messages.success(request, "Parking lot updated.")
        return redirect("lot_list")
    return render(request, "shared/form_page.html", {"form": form, "title": f"Edit {lot.name}", "submit_label": "Save"})


@login_required
def spot_list(request):
    lots = _lots_for(request.user)
    qs = ParkingSpot.objects.filter(parking_lot__in=lots).select_related("parking_lot")
    lot_id = request.GET.get("lot")
    status = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    if lot_id:
        qs = qs.filter(parking_lot_id=lot_id)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(notes__icontains=q))
    return render(request, "parking/spot_list.html", {
        "page_obj": _paginate(request, qs.order_by("parking_lot__name", "code")),
        "lots": lots,
        "statuses": ParkingSpot.Status.choices,
    })


@login_required
@manager_or_admin_required
@require_http_methods(["GET", "POST"])
def spot_create(request):
    form = ParkingSpotForm(request.POST or None)
    form.fields["parking_lot"].queryset = _lots_for(request.user)
    if request.method == "POST" and form.is_valid():
        spot = form.save(commit=False)
        if not request.user.is_platform_admin and not request.user.can_manage_unit(spot.parking_lot_id):
            raise PermissionDenied
        spot.full_clean()
        spot.save()
        audit(actor=request.user, parking_lot=spot.parking_lot, event_type="spot.created", obj=spot)
        messages.success(request, "Parking spot created.")
        return redirect("spot_list")
    return render(request, "shared/form_page.html", {"form": form, "title": "Create parking spot", "submit_label": "Save"})


@login_required
@manager_or_admin_required
@require_http_methods(["GET", "POST"])
def spot_edit(request, pk):
    spot = get_object_or_404(ParkingSpot.objects.select_related("parking_lot"), pk=pk, parking_lot__in=_lots_for(request.user))
    if not request.user.is_platform_admin and not request.user.can_manage_unit(spot.parking_lot_id):
        raise PermissionDenied
    form = ParkingSpotForm(request.POST or None, instance=spot)
    form.fields["parking_lot"].queryset = _lots_for(request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.full_clean()
        obj.save()
        audit(actor=request.user, parking_lot=obj.parking_lot, event_type="spot.updated", obj=obj)
        messages.success(request, "Parking spot updated.")
        return redirect("spot_list")
    return render(request, "shared/form_page.html", {"form": form, "title": f"Edit spot {spot.code}", "submit_label": "Save"})


@login_required
def vehicle_list(request):
    lot_ids = user_lot_ids(request.user)
    q = request.GET.get("q", "").strip()
    qs = Vehicle.objects.filter(Q(created_by=request.user) | Q(stays__parking_lot_id__in=lot_ids)).distinct()
    if request.user.is_platform_admin:
        qs = Vehicle.objects.all()
    if q:
        qs = qs.filter(Q(plate__icontains=q) | Q(make__icontains=q) | Q(model__icontains=q))
    return render(request, "parking/vehicle_list.html", {"page_obj": _paginate(request, qs.order_by("plate"))})


@login_required
@require_http_methods(["GET", "POST"])
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.created_by = request.user
        vehicle.save()
        messages.success(request, f"Vehicle {vehicle.plate} created.")
        return redirect("vehicle_list")
    return render(request, "shared/form_page.html", {"form": form, "title": "Create vehicle", "submit_label": "Save"})


@login_required
@require_http_methods(["GET", "POST"])
def vehicle_edit(request, pk):
    lot_ids = user_lot_ids(request.user)
    qs = Vehicle.objects.filter(Q(created_by=request.user) | Q(stays__parking_lot_id__in=lot_ids)).distinct()
    if request.user.is_platform_admin:
        qs = Vehicle.objects.all()
    vehicle = get_object_or_404(qs, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vehicle updated.")
        return redirect("vehicle_list")
    return render(request, "shared/form_page.html", {"form": form, "title": f"Edit {vehicle.plate}", "submit_label": "Save"})


@login_required
@require_http_methods(["GET", "POST"])
def stay_entry(request):
    form = EntryForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            result = enter_vehicle(
                actor=request.user,
                parking_lot=form.cleaned_data["parking_lot"],
                vehicle=form.cleaned_data["vehicle"],
                spot_id=form.cleaned_data["spot"].pk if form.cleaned_data["spot"] else None,
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
            messages.success(request, f"Entry registered. Spot: {result['spot']}.")
            return redirect("stay_active")
        except (OperationConflict, IdempotencyConflict, ValidationError) as exc:
            form.add_error(None, str(exc))
    return render(request, "shared/form_page.html", {"form": form, "title": "Register vehicle entry", "submit_label": "Register entry"})


@login_required
def stay_active(request):
    lots = _lots_for(request.user)
    qs = Stay.objects.filter(parking_lot__in=lots, status=Stay.Status.ACTIVE).select_related(
        "parking_lot", "spot", "vehicle", "tariff"
    )
    lot_id = request.GET.get("lot")
    q = request.GET.get("q", "").strip()
    if lot_id:
        qs = qs.filter(parking_lot_id=lot_id)
    if q:
        qs = qs.filter(Q(vehicle__plate__icontains=q) | Q(spot__code__icontains=q))
    return render(request, "parking/stay_active.html", {
        "page_obj": _paginate(request, qs),
        "lots": lots,
    })


@login_required
@require_http_methods(["GET", "POST"])
def stay_checkout(request, pk):
    stay = get_object_or_404(
        Stay.objects.select_related("parking_lot", "spot", "vehicle", "tariff"),
        pk=pk,
        parking_lot__in=_lots_for(request.user),
    )
    if stay.status != Stay.Status.ACTIVE:
        messages.info(request, "This stay is already closed.")
        return redirect("stay_detail", pk=stay.pk)

    quote = quote_stay(stay)
    form = CheckoutForm(request.POST or None, initial={"accepted_amount": quote["amount"]})
    if request.method == "POST" and form.is_valid():
        try:
            result = close_stay(
                actor=request.user,
                stay=stay,
                accepted_amount=form.cleaned_data["accepted_amount"],
                simulator_outcome=form.cleaned_data["simulator_outcome"],
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
            if result["closed"]:
                messages.success(request, f"Stay closed. Simulated receipt: {result['receipt_reference']}.")
                return redirect("stay_detail", pk=stay.pk)
            messages.error(request, "Simulated payment failed. The stay remains active and the spot remains occupied.")
            return redirect("stay_checkout", pk=stay.pk)
        except (OperationConflict, IdempotencyConflict, ValidationError) as exc:
            form.add_error(None, str(exc))
            quote = quote_stay(stay)
    return render(request, "parking/stay_checkout.html", {"stay": stay, "quote": quote, "form": form})


@login_required
def stay_history(request):
    lots = _lots_for(request.user)
    qs = Stay.objects.filter(parking_lot__in=lots, status=Stay.Status.CLOSED).select_related(
        "parking_lot", "spot", "vehicle", "tariff"
    )
    lot_id = request.GET.get("lot")
    q = request.GET.get("q", "").strip()
    selected_lots = lots
    if lot_id:
        selected_lots = lots.filter(pk=lot_id)
        qs = qs.filter(parking_lot_id=lot_id)
    if q:
        qs = qs.filter(Q(vehicle_plate_snapshot__icontains=q) | Q(spot_code_snapshot__icontains=q))
    start_date, end_date = _period_or_default(request)
    qs = _filter_by_local_period(
        qs, selected_lots, field="exited_at", start_date=start_date, end_date=end_date
    )
    return render(request, "parking/stay_history.html", {
        "page_obj": _paginate(request, qs),
        "lots": lots,
        "start_date": start_date,
        "end_date": end_date,
    })


@login_required
def stay_detail(request, pk):
    stay = get_object_or_404(
        Stay.objects.select_related("parking_lot", "spot", "vehicle", "tariff", "created_by", "closed_by"),
        pk=pk,
        parking_lot__in=_lots_for(request.user),
    )
    payments = stay.payments.select_related("created_by").all()
    return render(request, "parking/stay_detail.html", {"stay": stay, "payments": payments})


@login_required
@manager_or_admin_required
def tariff_list(request):
    lots = _lots_for(request.user)
    tariffs = TariffVersion.objects.filter(parking_lot__in=lots).select_related("parking_lot", "created_by")
    lot_id = request.GET.get("lot")
    if lot_id:
        tariffs = tariffs.filter(parking_lot_id=lot_id)
    return render(request, "billing/tariff_list.html", {"tariffs": tariffs, "lots": lots})


@login_required
@manager_or_admin_required
@require_http_methods(["GET", "POST"])
def tariff_create(request, lot_pk):
    lot = _get_lot_for_user(request.user, lot_pk)
    if not request.user.is_platform_admin and not request.user.can_manage_unit(lot.pk):
        raise PermissionDenied
    form = TariffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            tariff = create_tariff_version(parking_lot=lot, actor=request.user, **form.cleaned_data)
            messages.success(request, f"Tariff version {tariff.version} activated.")
            return redirect("tariff_list")
        except (ValidationError, PermissionError) as exc:
            form.add_error(None, str(exc))
    return render(request, "shared/form_page.html", {"form": form, "title": f"New tariff for {lot.name}", "submit_label": "Create version"})


@login_required
def payments_list(request):
    lots = _lots_for(request.user)
    qs = Payment.objects.filter(stay__parking_lot__in=lots).select_related(
        "stay", "stay__vehicle", "stay__parking_lot", "created_by"
    )
    lot_id = request.GET.get("lot")
    status_value = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    selected_lots = lots
    if lot_id:
        selected_lots = lots.filter(pk=lot_id)
        qs = qs.filter(stay__parking_lot_id=lot_id)
    if status_value:
        qs = qs.filter(status=status_value)
    if q:
        qs = qs.filter(Q(receipt_reference__icontains=q) | Q(stay__vehicle_plate_snapshot__icontains=q))
    start_date, end_date = _period_or_default(request)
    qs = _filter_by_local_period(
        qs, selected_lots, field="created_at", start_date=start_date, end_date=end_date,
        lot_lookup="stay__parking_lot",
    )
    return render(request, "billing/payment_list.html", {
        "page_obj": _paginate(request, qs),
        "lots": lots,
        "statuses": Payment.Status.choices,
        "start_date": start_date,
        "end_date": end_date,
    })


@login_required
@manager_or_admin_required
def audit_list(request):
    lots = _lots_for(request.user)
    if request.user.is_platform_admin:
        qs = AuditEvent.objects.filter(Q(parking_lot__in=lots) | Q(parking_lot__isnull=True))
    else:
        qs = AuditEvent.objects.filter(parking_lot__in=lots)
    qs = qs.select_related("actor", "parking_lot")
    lot_id = request.GET.get("lot")
    event_type = request.GET.get("event_type", "").strip()
    if lot_id:
        qs = qs.filter(parking_lot_id=lot_id)
    if event_type:
        qs = qs.filter(event_type__icontains=event_type)
    return render(request, "audit/audit_list.html", {"page_obj": _paginate(request, qs, 50), "lots": lots})


@login_required
@manager_or_admin_required
def export_stays_csv(request):
    lots = _lots_for(request.user)
    qs = Stay.objects.filter(parking_lot__in=lots).select_related(
        "parking_lot", "spot", "vehicle", "tariff"
    ).order_by("-entered_at")
    lot_id = request.GET.get("lot")
    status_value = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    selected_lots = lots
    if lot_id:
        selected_lots = lots.filter(pk=lot_id)
        qs = qs.filter(parking_lot_id=lot_id)
    if status_value:
        qs = qs.filter(status=status_value)
    if q:
        qs = qs.filter(Q(vehicle_plate_snapshot__icontains=q) | Q(spot_code_snapshot__icontains=q))
    try:
        start_date, end_date = parse_period(request.GET.get("start"), request.GET.get("end"))
    except PeriodError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    date_field = "exited_at" if status_value == Stay.Status.CLOSED else "entered_at"
    qs = _filter_by_local_period(
        qs, selected_lots, field=date_field, start_date=start_date, end_date=end_date
    )

    def rows():
        for stay in qs.iterator(chunk_size=500):
            yield [
                stay.pk,
                stay.parking_lot_code_snapshot,
                stay.vehicle_plate_snapshot,
                stay.spot_code_snapshot,
                stay.status,
                stay.entered_at.isoformat(),
                stay.exited_at.isoformat() if stay.exited_at else "",
                stay.final_amount if stay.final_amount is not None else "",
                stay.currency,
                stay.tariff.version,
            ]

    return streaming_csv(
        "stays.csv",
        ["id", "parking_lot", "vehicle_plate", "spot", "status", "entered_at_utc", "exited_at_utc", "final_amount", "currency", "tariff_version"],
        rows(),
    )


@login_required
@manager_or_admin_required
def export_payments_csv(request):
    lots = _lots_for(request.user)
    qs = Payment.objects.filter(stay__parking_lot__in=lots).select_related(
        "stay", "stay__parking_lot", "stay__vehicle"
    ).order_by("-created_at")
    lot_id = request.GET.get("lot")
    status_value = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    selected_lots = lots
    if lot_id:
        selected_lots = lots.filter(pk=lot_id)
        qs = qs.filter(stay__parking_lot_id=lot_id)
    if status_value:
        qs = qs.filter(status=status_value)
    if q:
        qs = qs.filter(Q(receipt_reference__icontains=q) | Q(stay__vehicle_plate_snapshot__icontains=q))
    try:
        start_date, end_date = parse_period(request.GET.get("start"), request.GET.get("end"))
    except PeriodError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain")
    qs = _filter_by_local_period(
        qs, selected_lots, field="created_at", start_date=start_date, end_date=end_date,
        lot_lookup="stay__parking_lot",
    )

    def rows():
        for p in qs.iterator(chunk_size=500):
            yield [
                p.pk, p.receipt_reference, p.stay.parking_lot_code_snapshot,
                p.stay.vehicle_plate_snapshot, p.amount, p.currency, p.status,
                p.simulated, p.created_at.isoformat()
            ]

    return streaming_csv(
        "payments.csv",
        ["id", "receipt_reference", "parking_lot", "vehicle_plate", "amount", "currency", "status", "simulated", "created_at_utc"],
        rows(),
    )


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
