from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts import views as account_views
from analyticsapp.views import dashboard
from parking import views
from parking.api import (
    ParkingLotViewSet, ParkingSpotViewSet, VehicleViewSet, StayViewSet,
    TariffViewSet, PaymentViewSet, api_entry, api_summary,
)

router = DefaultRouter()
router.register("parking-lots", ParkingLotViewSet, basename="api-parking-lot")
router.register("spots", ParkingSpotViewSet, basename="api-spot")
router.register("vehicles", VehicleViewSet, basename="api-vehicle")
router.register("stays", StayViewSet, basename="api-stay")
router.register("tariffs", TariffViewSet, basename="api-tariff")
router.register("payments", PaymentViewSet, basename="api-payment")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", views.health, name="health"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/change/", auth_views.PasswordChangeView.as_view(template_name="registration/password_change.html"), name="password_change"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),

    path("", dashboard, name="dashboard"),
    path("parking-lots/", views.lot_list, name="lot_list"),
    path("parking-lots/new/", views.lot_create, name="lot_create"),
    path("parking-lots/<int:pk>/edit/", views.lot_edit, name="lot_edit"),
    path("spots/", views.spot_list, name="spot_list"),
    path("spots/new/", views.spot_create, name="spot_create"),
    path("spots/<int:pk>/edit/", views.spot_edit, name="spot_edit"),
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
    path("vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path("stays/entry/", views.stay_entry, name="stay_entry"),
    path("stays/active/", views.stay_active, name="stay_active"),
    path("stays/history/", views.stay_history, name="stay_history"),
    path("stays/<int:pk>/", views.stay_detail, name="stay_detail"),
    path("stays/<int:pk>/checkout/", views.stay_checkout, name="stay_checkout"),
    path("tariffs/", views.tariff_list, name="tariff_list"),
    path("tariffs/<int:lot_pk>/new/", views.tariff_create, name="tariff_create"),
    path("payments/", views.payments_list, name="payments_list"),
    path("audit/", views.audit_list, name="audit_list"),
    path("exports/stays.csv", views.export_stays_csv, name="export_stays"),
    path("exports/payments.csv", views.export_payments_csv, name="export_payments"),

    path("users/", account_views.user_list, name="user_list"),
    path("users/new/", account_views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", account_views.user_edit, name="user_edit"),
    path("access/<int:pk>/toggle/", account_views.access_toggle, name="access_toggle"),

    path("api/v1/", include(router.urls)),
    path("api/v1/operations/entry/", api_entry, name="api-entry"),
    path("api/v1/reports/summary/", api_summary, name="api-summary"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
