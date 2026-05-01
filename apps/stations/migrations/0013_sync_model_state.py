# Синхронизация состояния моделей (simple_history + индексы) с актуальным кодом.

from django.db import migrations, models

from apps.stations.constants import SUBSCRIPTION_PLAN_CHOICES, SUBSCRIPTION_PLAN_FREE


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0012_car_brands"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="servicestation",
            new_name="stations_se_executo_34bba3_idx",
            old_name="stations_se_executo_2b8f7b_idx",
        ),
        migrations.AlterField(
            model_name="historicalservicestation",
            name="contact_phone",
            field=models.CharField(
                blank=True,
                help_text="Публичный номер. Если пусто — для авторизованных показывается телефон владельца.",
                max_length=20,
                verbose_name="Телефон для клиентов (E.164)",
            ),
        ),
        migrations.AlterField(
            model_name="historicalservicestation",
            name="instagram_url",
            field=models.URLField(blank=True, verbose_name="Instagram"),
        ),
        migrations.AlterField(
            model_name="historicalservicestation",
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
        migrations.AlterField(
            model_name="historicalservicestation",
            name="vk_url",
            field=models.URLField(blank=True, verbose_name="ВКонтакте"),
        ),
        migrations.AlterField(
            model_name="historicalservicestation",
            name="website",
            field=models.URLField(blank=True, verbose_name="Сайт"),
        ),
        migrations.AlterField(
            model_name="historicalservicestation",
            name="whatsapp_phone",
            field=models.CharField(
                blank=True,
                help_text="Для ссылки wa.me; можно совпадать с contact_phone.",
                max_length=20,
                verbose_name="WhatsApp (номер, E.164)",
            ),
        ),
    ]
