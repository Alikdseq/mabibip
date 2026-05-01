# Generated manually for environments without local GDAL.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0002_rename_audit_audit_event_t_6a55ab_idx_audit_audit_event_t_5dda62_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Короткое действие для фильтрации: create/update/delete/approve/etc.",
                max_length=40,
                verbose_name="Действие",
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="object_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Напр. users.User, stations.ServiceStation, bookings.Booking",
                max_length=80,
                verbose_name="Тип объекта",
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="object_id",
            field=models.BigIntegerField(blank=True, null=True, verbose_name="ID объекта"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_path",
            field=models.CharField(blank=True, default="", max_length=300, verbose_name="URL"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="method",
            field=models.CharField(blank=True, default="", max_length=10, verbose_name="Метод"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=300, verbose_name="User-Agent"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="status_code",
            field=models.SmallIntegerField(blank=True, null=True, verbose_name="HTTP статус"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["actor", "-created_at"], name="audit_actor_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["object_type", "object_id", "-created_at"],
                name="audit_obj_created_idx",
            ),
        ),
    ]

