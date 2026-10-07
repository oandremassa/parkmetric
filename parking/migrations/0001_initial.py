import parking.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ParkingLot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.SlugField(max_length=32, unique=True)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("timezone", models.CharField(default="Europe/Berlin", max_length=64, validators=[parking.models.validate_timezone])),
                ("currency", models.CharField(default="EUR", max_length=3)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plate", models.CharField(max_length=24)),
                ("country", models.CharField(default="DE", max_length=3)),
                ("make", models.CharField(blank=True, max_length=64)),
                ("model", models.CharField(blank=True, max_length=64)),
                ("color", models.CharField(blank=True, max_length=32)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["plate"]},
        ),
        migrations.CreateModel(
            name="ParkingSpot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32)),
                ("status", models.CharField(choices=[("free", "Free"), ("occupied", "Occupied"), ("blocked", "Blocked")], default="free", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parking_lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="spots", to="parking.parkinglot")),
            ],
            options={"ordering": ["parking_lot__name", "code"]},
        ),
        migrations.AddConstraint(
            model_name="vehicle",
            constraint=models.UniqueConstraint(fields=("plate", "country"), name="uniq_vehicle_plate_country"),
        ),
        migrations.AddConstraint(
            model_name="parkingspot",
            constraint=models.UniqueConstraint(fields=("parking_lot", "code"), name="uniq_spot_code_per_lot"),
        ),
    ]
