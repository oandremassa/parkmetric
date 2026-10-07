import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("parking", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TariffVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("name", models.CharField(default="Standard", max_length=80)),
                ("grace_minutes", models.PositiveIntegerField(default=10)),
                ("interval_minutes", models.PositiveIntegerField(default=60)),
                ("interval_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("daily_cap", models.DecimalField(decimal_places=2, max_digits=10)),
                ("effective_from", models.DateTimeField(default=django.utils.timezone.now)),
                ("effective_to", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_tariffs", to=settings.AUTH_USER_MODEL)),
                ("parking_lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tariffs", to="parking.parkinglot")),
            ],
            options={"ordering": ["parking_lot", "-version"]},
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.UniqueConstraint(fields=("parking_lot", "version"), name="uniq_tariff_version_per_lot"),
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.CheckConstraint(condition=models.Q(("interval_minutes__gt", 0)), name="tariff_interval_positive"),
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.CheckConstraint(condition=models.Q(("interval_price__gte", 0)), name="tariff_price_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.CheckConstraint(condition=models.Q(("daily_cap__gte", 0)), name="tariff_cap_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("effective_to__isnull", True), ("effective_to__gt", models.F("effective_from")), _connector="OR"),
                name="tariff_effective_range_valid",
            ),
        ),
    ]
