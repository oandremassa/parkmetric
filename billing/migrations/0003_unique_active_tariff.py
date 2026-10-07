from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_payment")]

    operations = [
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.UniqueConstraint(
                fields=("parking_lot",), condition=Q(is_active=True), name="uniq_active_tariff_per_lot"
            ),
        ),
    ]
