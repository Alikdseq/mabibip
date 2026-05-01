from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("classifieds", "0014_alter_autoshopprofile_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhoneRevealLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revealed_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Раскрыто")),
                (
                    "ad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phone_reveal_logs",
                        to="classifieds.ad",
                        verbose_name="Объявление",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phone_reveal_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "раскрытие телефона",
                "verbose_name_plural": "раскрытия телефонов",
                "ordering": ["-revealed_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="AdReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(blank=True, default="", max_length=500, verbose_name="Причина")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "ad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="classifieds.ad",
                        verbose_name="Объявление",
                    ),
                ),
                (
                    "reported_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ad_reports",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кто пожаловался",
                    ),
                ),
            ],
            options={
                "verbose_name": "жалоба на объявление",
                "verbose_name_plural": "жалобы на объявления",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="PhoneChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_phone", models.CharField(blank=True, default="", max_length=32, verbose_name="Старый телефон")),
                ("new_phone", models.CharField(blank=True, default="", max_length=32, verbose_name="Новый телефон")),
                ("changed_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Изменено")),
                ("ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phone_change_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "смена телефона",
                "verbose_name_plural": "смены телефона",
                "ordering": ["-changed_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="ImageHash",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phash", models.CharField(db_index=True, max_length=32, verbose_name="pHash")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "photo",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="image_hash",
                        to="classifieds.adphoto",
                        verbose_name="Фото",
                    ),
                ),
            ],
            options={
                "verbose_name": "хэш изображения",
                "verbose_name_plural": "хэши изображений",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.AddIndex(
            model_name="phonereveallog",
            index=models.Index(fields=["user", "-revealed_at"], name="clsfd_reveal_user_time"),
        ),
        migrations.AddIndex(
            model_name="phonereveallog",
            index=models.Index(fields=["ad", "-revealed_at"], name="clsfd_reveal_ad_time"),
        ),
        migrations.AddIndex(
            model_name="adreport",
            index=models.Index(fields=["ad", "-created_at"], name="clsfd_report_ad_time"),
        ),
        migrations.AddIndex(
            model_name="adreport",
            index=models.Index(fields=["reported_by", "-created_at"], name="clsfd_report_user_time"),
        ),
        migrations.AddIndex(
            model_name="phonechangelog",
            index=models.Index(fields=["user", "-changed_at"], name="clsfd_phonechg_user_time"),
        ),
        migrations.AddConstraint(
            model_name="adreport",
            constraint=models.UniqueConstraint(fields=("ad", "reported_by"), name="uniq_ad_report_ad_user"),
        ),
    ]

