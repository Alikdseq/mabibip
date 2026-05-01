from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(db_index=True, max_length=80, verbose_name="Тип события")),
                ("object_label", models.CharField(blank=True, default="", max_length=200, verbose_name="Объект")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Детали")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кто",
                    ),
                ),
            ],
            options={
                "verbose_name": "AuditLog",
                "verbose_name_plural": "AuditLog",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["event_type", "-created_at"], name="audit_audit_event_t_6a55ab_idx"),
        ),
    ]

