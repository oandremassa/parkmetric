from functools import wraps
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            raise PermissionDenied
        if not request.user.is_platform_admin:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped


def manager_or_admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            raise PermissionDenied
        if request.user.is_platform_admin or request.user.role == request.user.Role.MANAGER:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapped


def user_lot_ids(user):
    if not user.is_authenticated or not user.is_active:
        return []
    if user.is_platform_admin:
        from parking.models import ParkingLot
        return list(ParkingLot.objects.all().values_list("id", flat=True))
    return list(
        user.parking_accesses.filter(is_active=True)
        .values_list("parking_lot_id", flat=True)
    )
