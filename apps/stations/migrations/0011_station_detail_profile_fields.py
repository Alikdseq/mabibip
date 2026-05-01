# Карточка СТО / мастера: контакты, адрес, прайс, фото работ

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stations", "0010_catalog_filters"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicestation",
            name="address_public_mode",
            field=models.CharField(
                choices=[
                    ("full", "Полный адрес"),
                    ("district_only", "Только район"),
                    ("hidden_until_booking", "Точный адрес после записи"),
                ],
                default="full",
                max_length=30,
                verbose_name="Как показывать адрес",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="avatar",
            field=models.ImageField(
                blank=True,
                upload_to="stations/avatars/%Y/%m/",
                verbose_name="Фото мастера (аватар)",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="certified_partner",
            field=models.BooleanField(default=False, verbose_name="Сертифицированный сервис (плашка)"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="contact_phone",
            field=models.CharField(
                blank=True,
                help_text="Публичный номер. Если пусто — для авторизованных показывается телефон владельца.",
                max_length=20,
                verbose_name="Телефон для клиентов (E.164)",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="description_short",
            field=models.CharField(
                blank=True,
                help_text="Для шапки и SEO; основное описание ниже.",
                max_length=500,
                verbose_name="Краткое описание (до 500 симв.)",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="experience_years",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Опыт, лет"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="has_parking",
            field=models.BooleanField(default=False, verbose_name="Парковка для клиентов"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="inn",
            field=models.CharField(blank=True, max_length=12, verbose_name="ИНН"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="instagram_url",
            field=models.URLField(blank=True, verbose_name="Instagram"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="license_held",
            field=models.BooleanField(
                default=False,
                verbose_name="Лицензия / документы на проверке у админа",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="master_bio",
            field=models.TextField(blank=True, verbose_name="О мастере (расширенно)"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="ogrn",
            field=models.CharField(blank=True, max_length=15, verbose_name="ОГРН / ОГРНИП"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="tagline",
            field=models.CharField(
                blank=True,
                max_length=220,
                verbose_name="Специализация / слоган (частный мастер)",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="telegram_username",
            field=models.CharField(blank=True, max_length=64, verbose_name="Telegram (ник без @)"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="vk_url",
            field=models.URLField(blank=True, verbose_name="ВКонтакте"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="website",
            field=models.URLField(blank=True, verbose_name="Сайт"),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="whatsapp_phone",
            field=models.CharField(
                blank=True,
                help_text="Для ссылки wa.me; можно совпадать с contact_phone.",
                max_length=20,
                verbose_name="WhatsApp (номер, E.164)",
            ),
        ),
        migrations.AddField(
            model_name="servicestation",
            name="work_schedule_text",
            field=models.TextField(
                blank=True,
                help_text="Напр.: Пн–Пт 9:00–20:00, Сб 10:00–18:00, Вс — выходной.",
                verbose_name="График работы (текст)",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="address_public_mode",
            field=models.CharField(
                choices=[
                    ("full", "Полный адрес"),
                    ("district_only", "Только район"),
                    ("hidden_until_booking", "Точный адрес после записи"),
                ],
                default="full",
                max_length=30,
                verbose_name="Как показывать адрес",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="avatar",
            field=models.TextField(blank=True, max_length=100, verbose_name="Фото мастера (аватар)"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="certified_partner",
            field=models.BooleanField(default=False, verbose_name="Сертифицированный сервис (плашка)"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="contact_phone",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Публичный номер. Если пусто — для авторизованных показывается телефон владельца.",
                max_length=20,
                verbose_name="Телефон для клиентов (E.164)",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="description_short",
            field=models.CharField(
                blank=True,
                help_text="Для шапки и SEO; основное описание ниже.",
                max_length=500,
                verbose_name="Краткое описание (до 500 симв.)",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="experience_years",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Опыт, лет"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="has_parking",
            field=models.BooleanField(default=False, verbose_name="Парковка для клиентов"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="inn",
            field=models.CharField(blank=True, max_length=12, verbose_name="ИНН"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="instagram_url",
            field=models.CharField(blank=True, max_length=200, verbose_name="Instagram"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="license_held",
            field=models.BooleanField(
                default=False,
                verbose_name="Лицензия / документы на проверке у админа",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="master_bio",
            field=models.TextField(blank=True, verbose_name="О мастере (расширенно)"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="ogrn",
            field=models.CharField(blank=True, max_length=15, verbose_name="ОГРН / ОГРНИП"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="tagline",
            field=models.CharField(
                blank=True,
                max_length=220,
                verbose_name="Специализация / слоган (частный мастер)",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="telegram_username",
            field=models.CharField(blank=True, max_length=64, verbose_name="Telegram (ник без @)"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="vk_url",
            field=models.CharField(blank=True, max_length=200, verbose_name="ВКонтакте"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="website",
            field=models.CharField(blank=True, max_length=200, verbose_name="Сайт"),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="whatsapp_phone",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Для ссылки wa.me; можно совпадать с contact_phone.",
                max_length=20,
                verbose_name="WhatsApp (номер, E.164)",
            ),
        ),
        migrations.AddField(
            model_name="historicalservicestation",
            name="work_schedule_text",
            field=models.TextField(
                blank=True,
                help_text="Напр.: Пн–Пт 9:00–20:00, Сб 10:00–18:00, Вс — выходной.",
                verbose_name="График работы (текст)",
            ),
        ),
        migrations.AddField(
            model_name="stationphoto",
            name="caption",
            field=models.CharField(blank=True, max_length=200, verbose_name="Подпись"),
        ),
        migrations.AddField(
            model_name="stationphoto",
            name="is_work_sample",
            field=models.BooleanField(default=False, verbose_name="Пример работы (до/после)"),
        ),
        migrations.AddField(
            model_name="stationserviceoffer",
            name="note",
            field=models.CharField(blank=True, max_length=300, verbose_name="Примечание"),
        ),
        migrations.AddField(
            model_name="stationserviceoffer",
            name="service_title",
            field=models.CharField(
                blank=True,
                help_text="Если пусто — берётся название категории.",
                max_length=200,
                verbose_name="Название строки прайса",
            ),
        ),
    ]
