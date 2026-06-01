# -*- coding: utf-8 -*-

from __future__ import annotations

from apps.users.profile_completion import (
    business_profile_incomplete,
    profile_completion_checklist,
    profile_edit_url,
)


def profile_completion_banner(request):
    user = request.user
    if not business_profile_incomplete(user):
        return {}
    return {
        "show_profile_completion_banner": True,
        "profile_completion_edit_url": profile_edit_url(user),
        "profile_completion_checklist": profile_completion_checklist(user),
    }
