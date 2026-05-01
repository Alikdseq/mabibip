from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class AllowedFileType:
    ext: str
    magic_prefixes: tuple[bytes, ...]


ALLOWED = (
    AllowedFileType(ext="pdf", magic_prefixes=(b"%PDF-",)),
    AllowedFileType(ext="png", magic_prefixes=(b"\x89PNG\r\n\x1a\n",)),
    AllowedFileType(ext="jpg", magic_prefixes=(b"\xff\xd8\xff",)),
    AllowedFileType(ext="jpeg", magic_prefixes=(b"\xff\xd8\xff",)),
)


def validate_chat_attachment(uploaded) -> None:
    """
    B.5: MIME + magic bytes.
    Здесь делаем строгое проверочное чтение magic bytes и расширения.
    """
    if uploaded is None:
        return

    max_bytes = int(getattr(settings, "CHAT_ATTACHMENT_MAX_BYTES", 5 * 1024 * 1024))
    if getattr(uploaded, "size", 0) > max_bytes:
        raise ValidationError(f"Файл слишком большой (макс. {max_bytes} байт).")

    name = (getattr(uploaded, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    allowed = {a.ext for a in ALLOWED}
    if ext not in allowed:
        raise ValidationError("Разрешены только jpg/png/pdf.")

    # magic bytes
    pos = uploaded.tell() if hasattr(uploaded, "tell") else None
    try:
        head = uploaded.read(16)
    finally:
        try:
            if pos is not None:
                uploaded.seek(pos)
        except Exception:
            pass

    for a in ALLOWED:
        if a.ext == ext and any(head.startswith(p) for p in a.magic_prefixes):
            return
    raise ValidationError("Неверный формат файла (magic bytes не совпадают).")

