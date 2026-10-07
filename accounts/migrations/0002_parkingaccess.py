import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
        ("parking", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParkingAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parking_lot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_accesses", to="parking.parkinglot")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parking_accesses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["parking_lot__name", "user__username"]},
        ),
        migrations.AddConstraint(
            model_name="parkingaccess",
            constraint=models.UniqueConstraint(fields=("user", "parking_lot"), name="uniq_user_parking_access"),
        ),
    ]
