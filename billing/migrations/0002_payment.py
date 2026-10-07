import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0001_initial"),
        ("parking", "0002_stay"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("status", models.CharField(choices=[("succeeded", "Succeeded"), ("failed", "Failed"), ("waived", "Waived")], max_length=16)),
                ("simulated", models.BooleanField(default=True)),
                ("simulator_reason", models.CharField(blank=True, max_length=120)),
                ("receipt_reference", models.CharField(max_length=48, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to=settings.AUTH_USER_MODEL)),
                ("stay", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="parking.stay")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["succeeded", "waived"])),
                fields=("stay",),
                name="uniq_successful_payment_per_stay",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gte", 0)), name="payment_amount_nonnegative"),
        ),
    ]
