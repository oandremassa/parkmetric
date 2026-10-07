from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response

from accounts.permissions import user_lot_ids
from analyticsapp.filters import PeriodError, parse_period
from analyticsapp.services import historical_metrics
from auditlog.services import IdempotencyConflict
from billing.models import Payment, TariffVersion
from .models import ParkingLot, ParkingSpot, Stay, Vehicle
from .services import OperationConflict, close_stay, enter_vehicle, quote_stay


class ParkingLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParkingLot
        fields = ["id", "name", "code", "address", "timezone", "currency", "is_active"]


class ParkingSpotSerializer(serializers.ModelSerializer):
    parking_lot_name = serializers.CharField(source="parking_lot.name", read_only=True)

    class Meta:
        model = ParkingSpot
        fields = ["id", "parking_lot", "parking_lot_name", "code", "status", "is_active", "notes"]


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "plate", "country", "make", "model", "color", "notes", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        plate = "".join(attrs.get("plate", "").upper().split())
        country = attrs.get("country", "DE").upper()
        if not plate:
            raise serializers.ValidationError({"plate": "Plate is required."})
        attrs["plate"] = plate
        attrs["country"] = country
        if Vehicle.objects.filter(plate=plate, country=country).exists():
            raise serializers.ValidationError({"plate": "A vehicle with this plate and country already exists."})
        return attrs


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = TariffVersion
        fields = [
            "id", "parking_lot", "version", "name", "grace_minutes", "interval_minutes",
            "interval_price", "daily_cap", "effective_from", "effective_to", "is_active",
        ]


class StaySerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source="vehicle.plate", read_only=True)
    spot_code = serializers.CharField(source="spot.code", read_only=True)
    parking_lot_code = serializers.CharField(source="parking_lot.code", read_only=True)
    tariff_version = serializers.IntegerField(source="tariff.version", read_only=True)

    class Meta:
        model = Stay
        fields = [
            "id", "parking_lot", "parking_lot_code", "spot", "spot_code", "vehicle", "vehicle_plate",
            "tariff", "tariff_version", "status", "entered_at", "exited_at", "final_amount",
            "currency", "zero_charge_reason", "vehicle_plate_snapshot", "spot_code_snapshot",
            "parking_lot_code_snapshot",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    parking_lot = serializers.IntegerField(source="stay.parking_lot_id", read_only=True)
    vehicle_plate = serializers.CharField(source="stay.vehicle_plate_snapshot", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "stay", "parking_lot", "vehicle_plate", "amount", "currency", "status",
            "simulated", "simulator_reason", "receipt_reference", "created_at",
        ]


class ScopedReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    lot_lookup = "parking_lot_id"

    def allowed_lot_ids(self):
        return user_lot_ids(self.request.user)


class ParkingLotViewSet(ScopedReadOnlyViewSet):
    serializer_class = ParkingLotSerializer

    def get_queryset(self):
        return ParkingLot.objects.filter(pk__in=self.allowed_lot_ids()).order_by("name")


class ParkingSpotViewSet(ScopedReadOnlyViewSet):
    serializer_class = ParkingSpotSerializer

    def get_queryset(self):
        qs = ParkingSpot.objects.filter(parking_lot_id__in=self.allowed_lot_ids()).select_related("parking_lot")
        lot = self.request.query_params.get("parking_lot")
        status_value = self.request.query_params.get("status")
        if lot:
            qs = qs.filter(parking_lot_id=lot)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs.order_by("parking_lot__name", "code")


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        lot_ids = user_lot_ids(self.request.user)
        from django.db.models import Q
        qs = Vehicle.objects.filter(Q(created_by=self.request.user) | Q(stays__parking_lot_id__in=lot_ids)).distinct()
        if self.request.user.is_platform_admin:
            qs = Vehicle.objects.all()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(plate__icontains=q)
        return qs.order_by("plate")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StayViewSet(ScopedReadOnlyViewSet):
    serializer_class = StaySerializer

    def get_queryset(self):
        qs = Stay.objects.filter(parking_lot_id__in=self.allowed_lot_ids()).select_related(
            "parking_lot", "spot", "vehicle", "tariff"
        )
        lot = self.request.query_params.get("parking_lot")
        status_value = self.request.query_params.get("status")
        if lot:
            qs = qs.filter(parking_lot_id=lot)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs.order_by("-entered_at")

    @action(detail=True, methods=["get"])
    def quote(self, request, pk=None):
        stay = self.get_object()
        try:
            return Response(quote_stay(stay))
        except OperationConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        stay = self.get_object()
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise DRFValidationError({"Idempotency-Key": "This header is required."})
        try:
            result = close_stay(
                actor=request.user,
                stay=stay,
                accepted_amount=serializer.validated_data["accepted_amount"],
                simulator_outcome=serializer.validated_data["simulator_outcome"],
                idempotency_key=key,
            )
        except IdempotencyConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except OperationConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        response_status = status.HTTP_200_OK if result.get("closed") else status.HTTP_402_PAYMENT_REQUIRED
        return Response(result, status=response_status)


class TariffViewSet(ScopedReadOnlyViewSet):
    serializer_class = TariffSerializer

    def get_queryset(self):
        return TariffVersion.objects.filter(parking_lot_id__in=self.allowed_lot_ids()).order_by(
            "parking_lot_id", "-version"
        )


class PaymentViewSet(ScopedReadOnlyViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(stay__parking_lot_id__in=self.allowed_lot_ids()).select_related(
            "stay", "stay__vehicle"
        ).order_by("-created_at")


class EntryRequestSerializer(serializers.Serializer):
    parking_lot = serializers.PrimaryKeyRelatedField(queryset=ParkingLot.objects.none())
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.none())
    spot = serializers.PrimaryKeyRelatedField(queryset=ParkingSpot.objects.none(), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return
        from django.db.models import Q
        lot_ids = user_lot_ids(request.user)
        self.fields["parking_lot"].queryset = ParkingLot.objects.filter(pk__in=lot_ids, is_active=True)
        self.fields["spot"].queryset = ParkingSpot.objects.filter(parking_lot_id__in=lot_ids, is_active=True)
        vehicles = Vehicle.objects.filter(is_active=True)
        if not request.user.is_platform_admin:
            vehicles = vehicles.filter(Q(created_by=request.user) | Q(stays__parking_lot_id__in=lot_ids)).distinct()
        self.fields["vehicle"].queryset = vehicles

    def validate(self, attrs):
        lot = attrs["parking_lot"]
        spot = attrs.get("spot")
        if spot and spot.parking_lot_id != lot.pk:
            raise serializers.ValidationError("Spot does not belong to the selected parking lot.")
        return attrs


class CheckoutRequestSerializer(serializers.Serializer):
    accepted_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    simulator_outcome = serializers.ChoiceField(choices=["success", "failure"])


@api_view(["POST"])
def api_entry(request):
    serializer = EntryRequestSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise DRFValidationError({"Idempotency-Key": "This header is required."})
    try:
        result = enter_vehicle(
            actor=request.user,
            parking_lot=serializer.validated_data["parking_lot"],
            vehicle=serializer.validated_data["vehicle"],
            spot_id=serializer.validated_data.get("spot").pk if serializer.validated_data.get("spot") else None,
            idempotency_key=key,
        )
        return Response(result, status=status.HTTP_201_CREATED)
    except IdempotencyConflict as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    except OperationConflict as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


@api_view(["GET"])
def api_summary(request):
    if not (request.user.is_platform_admin or request.user.role == request.user.Role.MANAGER):
        raise PermissionDenied("Reports require manager or administrator access.")
    lot_id = request.query_params.get("parking_lot")
    if not lot_id or not str(lot_id).isdigit():
        raise DRFValidationError({"parking_lot": "A parking_lot id is required."})
    if int(lot_id) not in user_lot_ids(request.user):
        raise NotFound()
    lot = get_object_or_404(ParkingLot, pk=lot_id)
    try:
        start, end = parse_period(request.query_params.get("start"), request.query_params.get("end"))
    except PeriodError as exc:
        raise DRFValidationError({"period": str(exc)}) from exc
    return Response(historical_metrics(lot, start, end))
