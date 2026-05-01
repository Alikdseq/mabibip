from __future__ import annotations

from django.contrib.admin.apps import AdminConfig


class ProMasterAdminConfig(AdminConfig):
    default_site = "config.admin_site.ProMasterAdminSite"

