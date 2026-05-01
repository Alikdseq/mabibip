"""Теги шаблонов каталога СТО."""

from __future__ import annotations

from pathlib import Path
import unicodedata
from urllib.parse import urlencode

from django import template
from django.conf import settings

from apps.stations.display import station_contact_phone_e164

register = template.Library()

_LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

# Логический ключ марки (как в БД / logo_png_stem) → фактическое имя файла без расширения.
_LOGO_FILE_STEM_ALIASES: dict[str, str] = {
    "peugeot": "pageut",
    "renault": "reno",
}


def _brand_logo_dir() -> Path:
    """
    В разных settings.BASE_DIR может быть /app или /app/config.
    Логотипы лежат в <repo>/static/logo.
    """
    base = Path(settings.BASE_DIR)
    candidates = [
        base / "static" / "logo",
        base.parent / "static" / "logo",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def _try_stems_for_brand(raw: str) -> list[str]:
    """Порядок: сначала алиас файла (pageut, reno), затем каноническое имя."""
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[str] = []
    lk = raw.lower()
    if lk in _LOGO_FILE_STEM_ALIASES:
        out.append(_LOGO_FILE_STEM_ALIASES[lk])
    out.append(raw)
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _norm_logo_stem(raw: str) -> str:
    """
    Нормализация имён логотипов для поиска файлов:
    - приводим к lower
    - убираем диакритику (Citroën -> citroen)
    - убираем пробелы/дефисы/подчёркивания и прочие не-буквенно-цифровые символы
    """
    s = (raw or "").strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    return "".join(ch for ch in s if ch.isalnum())


@register.filter
def brand_logo_relpath(stem: str) -> str:
    """Путь для {% static %}: logo/<файл>. Алиасы имён, регистр (Linux/Docker), jpg/webp."""
    raw = (stem or "").strip()
    if not raw:
        return "logo/.png"
    d = _brand_logo_dir()
    default = f"logo/{raw}.png"
    if not d.is_dir():
        return default
    try_stems = _try_stems_for_brand(raw)
    try_lower = {s.lower() for s in try_stems}
    try_norm = {_norm_logo_stem(s) for s in try_stems if _norm_logo_stem(s)}
    raw_norm = _norm_logo_stem(raw)
    for name in try_stems:
        for ext in _LOGO_SUFFIXES:
            p = d / f"{name}{ext}"
            if p.is_file():
                return f"logo/{p.name}"
    try:
        for p in d.iterdir():
            if not p.is_file() or p.suffix.lower() not in _LOGO_SUFFIXES:
                continue
            stem_l = p.stem.lower()
            if stem_l in try_lower or stem_l == raw.lower():
                return f"logo/{p.name}"
            # Файлы с пробелами/диакритикой: "land rover.png", "citroën.png" и т.п.
            pn = _norm_logo_stem(p.stem)
            if pn and (pn == raw_norm or pn in try_norm):
                return f"logo/{p.name}"
    except OSError:
        return default
    return default


@register.filter
def brand_logo_size(stem: str) -> int:
    """Сторона логотипа (px): Renault ×2 от прежнего; VW меньше; часть марок слегка крупнее базы."""
    s = (stem or "").strip().lower()
    if s in ("volkswagen", "vw"):
        return 58
    if s == "renault":
        return 96
    if s in frozenset({"lada", "nissan", "hyundai", "skoda", "geely"}):
        return 100
    if s in frozenset({"toyota", "peugeot"}):
        return 104
    if s in frozenset({"bmw", "audi"}):
        return 96
    if s == "ford":
        return 96
    return 80


@register.filter
def dict_get(mapping, key):
    if not mapping:
        return ""
    return mapping.get(key, "")


@register.filter
def distance_as_km(d):
    """Аннотация Distance / число метров → км для шаблона."""
    if d is None:
        return ""


@register.simple_tag
def station_phone_e164(station) -> str:
    """Телефон для кнопки «Позвонить» с учётом мастеров автосервиса (parent_station)."""
    try:
        return station_contact_phone_e164(station)
    except Exception:
        return ""
    try:
        if hasattr(d, "km"):
            return f"{float(d.km):.1f}"
        return f"{float(d) / 1000:.1f}"
    except (TypeError, ValueError):
        return ""


@register.simple_tag
def catalog_querystring(request_get, page=None):
    """Сохраняет GET-параметры для пагинации и ссылок сортировки."""
    pairs = []
    for key in sorted(request_get.keys()):
        if key == "page":
            continue
        for v in request_get.getlist(key):
            pairs.append((key, v))
    if page is not None:
        pairs.append(("page", str(page)))
    return urlencode(pairs)
