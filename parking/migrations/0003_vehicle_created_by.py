import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("parking", "0002_stay"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_vehicles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
