from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ParkingAccessForm, UserCreateForm, UserEditForm
from .models import ParkingAccess, User
from .permissions import admin_required
from auditlog.services import audit


@login_required
@admin_required
def user_list(request):
    users = User.objects.all().order_by("username")
    return render(request, "accounts/user_list.html", {"users": users})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        audit(actor=request.user, parking_lot=None, event_type="user.created", obj=user, detail={"role": user.role})
        messages.success(request, f"User {user.username} created.")
        return redirect("user_edit", pk=user.pk)
    return render(request, "shared/form_page.html", {"form": form, "title": "Create user", "submit_label": "Create user"})


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    access_form = ParkingAccessForm(prefix="access")
    if request.method == "POST":
        action = request.POST.get("action", "save_user")
        if action == "save_user" and form.is_valid():
            if user.pk == request.user.pk and not form.cleaned_data["is_active"]:
                form.add_error("is_active", "You cannot deactivate your own account.")
            else:
                updated = form.save()
                audit(
                    actor=request.user, parking_lot=None, event_type="user.updated", obj=updated,
                    detail={"role": updated.role, "is_active": updated.is_active},
                )
                messages.success(request, "Account updated.")
                return redirect("user_edit", pk=user.pk)
        elif action == "add_access":
            access_form = ParkingAccessForm(request.POST, prefix="access")
            if access_form.is_valid():
                access, created = ParkingAccess.objects.update_or_create(
                    user=user,
                    parking_lot=access_form.cleaned_data["parking_lot"],
                    defaults={"is_active": access_form.cleaned_data["is_active"]},
                )
                audit(
                    actor=request.user, parking_lot=access.parking_lot, event_type="access.updated", obj=access,
                    detail={"user_id": user.pk, "is_active": access.is_active},
                )
                messages.success(request, "Parking access saved.")
                return redirect("user_edit", pk=user.pk)
    accesses = user.parking_accesses.select_related("parking_lot").all()
    return render(request, "accounts/user_edit.html", {
        "edited_user": user,
        "form": form,
        "access_form": access_form,
        "accesses": accesses,
    })


@login_required
@admin_required
@require_http_methods(["POST"])
def access_toggle(request, pk):
    access = get_object_or_404(ParkingAccess, pk=pk)
    access.is_active = not access.is_active
    access.save(update_fields=["is_active"])
    audit(
        actor=request.user, parking_lot=access.parking_lot, event_type="access.toggled", obj=access,
        detail={"user_id": access.user_id, "is_active": access.is_active},
    )
    messages.success(request, "Parking access updated.")
    return redirect("user_edit", pk=access.user_id)
