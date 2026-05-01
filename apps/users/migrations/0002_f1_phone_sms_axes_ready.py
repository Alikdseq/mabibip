# Generated manually — фаза F1: телефон как логин, SMS-вызовы, email опционален.

from django.db import migrations, models


def assign_phones_forward(apps, schema_editor):
    User = apps.get_model("users", "User")
    for u in User.objects.all():
        phone = (getattr(u, "phone", None) or "").strip()
        if not phone:
            u.phone = f"+7999000{u.pk:07d}"
        u.is_phone_verified = True
        u.save(update_fields=["phone", "is_phone_verified"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhoneVerificationChallenge",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("phone_e164", models.CharField(db_index=True, max_length=16)),
                ("code_hash", models.CharField(max_length=64)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_ip", models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "запрос кода по телефону",
                "verbose_name_plural": "запросы кодов по телефону",
            },
        ),
        migrations.AddIndex(
            model_name="phoneverificationchallenge",
            index=models.Index(fields=["phone_e164", "-created_at"], name="users_pvc_phone_cr_idx"),
        ),
        migrations.AddField(
            model_name="user",
            name="is_phone_verified",
            field=models.BooleanField(default=False, verbose_name="Телефон подтверждён"),
        ),
        migrations.RunPython(assign_phones_forward, noop_reverse),
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(
                db_index=True,
                max_length=16,
                unique=True,
                verbose_name="Телефон (E.164)",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                unique=True,
                verbose_name="Электронная почта",
            ),
        ),
    ]
