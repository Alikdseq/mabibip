from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .models import AuditLog


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Минимизация ПДн в аудит-логах.
    AuditLog предназначен для доказательной базы действий, а не для хранения пользовательских данных.
    """
    if not payload:
        return {}

    redact_keys = {
        "phone",
        "phone_e164",
        "contact_phone",
        "email",
        "address",
        "vin",
        "license_plate",
        "gosnomer",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "cookies",
        "password",
        "otp",
        "code",
    }

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                lk = str(k).lower()
                if lk in redact_keys:
                    out[k] = "[redacted]"
                else:
                    out[k] = scrub(v)
            return out
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    return scrub(payload)


def client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
        return ip or None
    return request.META.get("REMOTE_ADDR")


def audit_log(
    *,
    request: HttpRequest | None,
    event_type: str,
    action: str = "",
    obj: Any | None = None,
    object_label: str = "",
    payload: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> AuditLog:
    """
    Единая точка записи аудита.
    - request (опционально): если есть, проставляем ip/path/method/user_agent/actor.
    - obj (опционально): если Django model instance, проставляем object_type/object_id.
    """

    actor = None
    ip_address = None
    request_path = ""
    method = ""
    user_agent = ""

    if request is not None:
        user = getattr(request, "user", None)
        actor = user if getattr(user, "is_authenticated", False) else None
        ip_address = client_ip(request)
        request_path = (getattr(request, "path", "") or "")[:300]
        method = (getattr(request, "method", "") or "")[:10]
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:300]

    object_type = ""
    object_id = None
    if obj is not None:
        meta = getattr(obj, "_meta", None)
        pk = getattr(obj, "pk", None)
        if meta is not None and pk is not None:
            object_type = getattr(meta, "label", "") or ""
            object_id = int(pk)

    return AuditLog.objects.create(
        actor=actor,
        event_type=event_type,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_label=object_label or "",
        payload=_redact_payload(payload or {}),
        ip_address=ip_address,
        request_path=request_path,
        method=method,
        user_agent=user_agent,
        status_code=status_code,
    )

