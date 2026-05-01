from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_rename_users_pvc_phone_cr_idx_users_phone_phone_e_00ad69_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(db_index=True, max_length=32, unique=True, verbose_name="Телефон (E.164)"),
        ),
    ]

