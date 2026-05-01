# Generated manually for email verification (МаБибип / ТЗ защита регистрации).

from django.db import migrations, models


def set_existing_users_email_verified(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_alter_favoritestation_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified",
            field=models.BooleanField(
                default=False,
                verbose_name="Email подтверждён",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verification_token",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="Токен подтверждения email",
                db_index=True,
            ),
        ),
        migrations.RunPython(set_existing_users_email_verified, migrations.RunPython.noop),
    ]
