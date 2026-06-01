# -*- coding: utf-8 -*-

from apps.stations.display import _user_public_display_name


def help_author_label(user) -> str:
    return _user_public_display_name(user)


def help_author_phone_e164(user) -> str:
    phone = (getattr(user, "contact_phone", None) or "").strip()
    if phone:
        return phone
    return (getattr(user, "phone", None) or "").strip()
