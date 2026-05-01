# Generated manually for environments without local GDAL.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_auditlog_request_object_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["request_path", "-created_at"], name="audit_path_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["status_code", "-created_at"], name="audit_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["method", "-created_at"], name="audit_method_created_idx"),
        ),
    ]

