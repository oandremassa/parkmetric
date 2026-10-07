import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0001_initial"),
        ("parking", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Stay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("active", "Active"), ("closed", "Closed")], default="active", max_length=16)),
                ("entered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("exited_at", models.DateTimeField(blank=True, null=True)),
                ("final_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(max_length=3)),
                ("zero_charge_reason", models.CharField(blank=True, max_length=120)),
                ("vehicle_plate_snapshot", models.CharField(max_length=24)),
                ("spot_code_snapshot", models.CharField(max_length=32)),
                ("parking_lot_code_snapshot", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="closed_stays", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_stays", to=settings.AUTH_USER_MODEL)),
                ("parking_lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stays", to="parking.parkinglot")),
                ("spot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stays", to="parking.parkingspot")),
                ("tariff", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stays", to="billing.tariffversion")),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stays", to="parking.vehicle")),
            ],
            options={"ordering": ["-entered_at"]},
        ),
        migrations.AddConstraint(
            model_name="stay",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("spot",), name="uniq_active_stay_per_spot"),
        ),
        migrations.AddConstraint(
            model_name="stay",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("parking_lot", "vehicle"), name="uniq_active_vehicle_per_lot"),
        ),
        migrations.AddConstraint(
            model_name="stay",
            constraint=models.CheckConstraint(
                condition=models.Q(("exited_at__isnull", True), ("exited_at__gte", models.F("entered_at")), _connector="OR"),
                name="stay_exit_not_before_entry",
            ),
        ),
        migrations.AddConstraint(
            model_name="stay",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("status", "active"), ("exited_at__isnull", True)),
                    models.Q(("status", "closed"), ("exited_at__isnull", False)),
                    _connector="OR",
                ),
                name="stay_status_exit_consistency",
            ),
        ),
    ]
