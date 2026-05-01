from django.db import migrations, models

from apps.stations.constants import SUBSCRIPTION_PLAN_FREE, SUBSCRIPTION_PLAN_CHOICES


class Migration(migrations.Migration):
    dependencies = [
        ("stations", "0007_alter_historicalservicestation_billing_blocked_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicestation",
            name="subscription_plan",
            field=models.CharField(
                choices=SUBSCRIPTION_PLAN_CHOICES,
                default=SUBSCRIPTION_PLAN_FREE,
                help_text=(
                    "Free — в каталоге без проверки оплаты. "
                    "Basic — в каталоге только при заполненной дате «оплачено до» не раньше текущего дня."
                ),
                max_length=20,
                verbose_name="Тариф",
            ),
        ),
    ]

