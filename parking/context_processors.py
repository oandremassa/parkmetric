from accounts.permissions import user_lot_ids
from .models import ParkingLot


def navigation_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    lot_ids = user_lot_ids(request.user)
    lots = ParkingLot.objects.filter(pk__in=lot_ids, is_active=True).order_by("name")
    selected = None
    raw = request.GET.get("lot") or request.POST.get("parking_lot")
    if raw and str(raw).isdigit():
        selected = lots.filter(pk=int(raw)).first()
    if not selected:
        selected = lots.first()
    return {"nav_parking_lots": lots, "nav_selected_lot": selected}
