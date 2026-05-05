"""Город посетителя: сессия, справочник районов, подписи в шапке и каталоге."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

SESSION_KEY = "visitor_city_label"

# Если файл ru_cities.txt недоступен и в БД нет District.city_label — чтобы формы не были пустыми.
RU_CITY_LABELS_FALLBACK: tuple[str, ...] = (
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Краснодар",
    "Саратов",
    "Тюмень",
    "Тольятти",
    "Ижевск",
    "Барнаул",
    "Ульяновск",
    "Иркутск",
    "Хабаровск",
    "Ярославль",
    "Владивосток",
    "Махачкала",
    "Томск",
    "Оренбург",
    "Кемерово",
    "Новокузнецк",
    "Рязань",
    "Астрахань",
    "Пенза",
    "Липецк",
    "Тула",
    "Киров",
    "Чебоксары",
    "Калининград",
    "Брянск",
    "Иваново",
    "Магнитогорск",
    "Сочи",
    "Ставрополь",
)


def list_allowed_city_labels() -> list[str]:
    labels = _load_ru_city_labels()
    # Совместимость: если справочник пуст — берём подписи городов из District.
    if not labels:
        from apps.stations.models import District

        labels = sorted(
            {
                x.strip()
                # Это справочная информация, не требующая read-replica маршрутизации.
                for x in District.objects.using("default")
                .exclude(city_label="")
                .values_list("city_label", flat=True)
                if (x or "").strip()
            },
            key=str.casefold,
        )

    if not labels:
        logger.warning(
            "Список городов пуст (нет ru_cities.txt, нет District.city_label) — используется встроенный fallback."
        )
        labels = list(RU_CITY_LABELS_FALLBACK)

    # Фокус-город (если задан) не ограничивает список, а лишь «поднимается» вверх.
    # По умолчанию «поднимаем» Владикавказ (основной город проекта).
    focus = (getattr(settings, "APP_FOCUS_CITY_LABEL", None) or "").strip() or "Владикавказ"
    if focus:
        rest = [x for x in labels if x.casefold() != focus.casefold()]
        return [focus] + rest if any(x.casefold() == focus.casefold() for x in labels) else labels
    return labels


def _load_ru_city_labels() -> list[str]:
    """
    Справочник городов РФ для выпадающих списков.
    Лежит в репозитории: apps/core/data/ru_cities.txt (1 город = 1 строка).
    Путь рядом с пакетом — надёжнее, чем только BASE_DIR (редкий неверный cwd в воркере).
    Без lru_cache: пустой результат при первом чтении не должен «залипать» до рестарта.
    """
    base = Path(getattr(settings, "BASE_DIR", ".")).resolve()
    pkg_dir = Path(__file__).resolve().parent
    candidates = [
        pkg_dir / "data" / "ru_cities.txt",
        base / "apps" / "core" / "data" / "ru_cities.txt",
        base.parent / "apps" / "core" / "data" / "ru_cities.txt",
    ]
    p = next((c for c in candidates if c.is_file()), None)
    if not p:
        logger.warning("Файл ru_cities.txt не найден по путям: %s", candidates)
        return []
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read ru_cities.txt")
        return []
    out: list[str] = []
    for line in raw.splitlines():
        s = (line or "").strip()
        if not s or s.startswith("#") or s.startswith("```"):
            continue
        out.append(s)
    # uniq + stable order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        k = x.casefold()
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def _pick_default_label(allowed: list[str]) -> str:
    if not allowed:
        return ""
    env = (getattr(settings, "VISITOR_DEFAULT_CITY_LABEL", None) or "").strip()
    if env and env in allowed:
        return env
    return allowed[0]


def guess_city_label_from_request(request: HttpRequest) -> str | None:
    """Опционально: GeoIP2 + каталог городов. Без БД MaxMind и пакета geoip2 всегда None."""
    if not getattr(settings, "VISITOR_CITY_GUESS_FROM_IP", False):
        return None
    try:
        from django.contrib.gis.geoip2 import GeoIP2
    except Exception:
        return None
    geo_path = getattr(settings, "GEOIP_PATH", None) or getattr(settings, "GEOIP_CITY_PATH", None)
    if not geo_path:
        return None
    ip = (request.META.get("REMOTE_ADDR") or "").strip()
    if not ip or ip == "127.0.0.1":
        return None
    allowed = list_allowed_city_labels()
    if not allowed:
        return None
    try:
        g = GeoIP2(path=geo_path)
        info = g.city(ip)
        city = (info.get("city") or "").strip()
    except Exception:
        logger.debug("GeoIP city lookup failed", exc_info=True)
        return None
    if not city:
        return None
    for label in allowed:
        if label.casefold() == city.casefold():
            return label
    return None


def ensure_visitor_city_in_session(request: HttpRequest) -> None:
    """Выставляет город в сессии при первом заходе и чинит устаревшие значения."""
    allowed = list_allowed_city_labels()
    # Один расчёт списка на запрос: контекст-процессор переиспользует (без повторного чтения файла/БД).
    request._visitor_city_allowed_labels = allowed
    if not allowed:
        return
    raw = (request.session.get(SESSION_KEY) or "").strip()
    if raw in allowed:
        return
    guessed = guess_city_label_from_request(request)
    if guessed and guessed in allowed:
        request.session[SESSION_KEY] = guessed
        return
    request.session[SESSION_KEY] = _pick_default_label(allowed)


def visitor_city_context(request: HttpRequest) -> dict:
    from django.urls import reverse

    labels = getattr(request, "_visitor_city_allowed_labels", None)
    if labels is None:
        labels = list_allowed_city_labels()
    sess = getattr(request, "session", None)
    get_sess = (sess.get if hasattr(sess, "get") else (lambda _k, _d=None: _d))  # type: ignore[attr-defined]
    label = (get_sess(SESSION_KEY, "") or "").strip() if labels else ""
    if labels and label not in labels:
        label = _pick_default_label(labels)
    return {
        "visitor_city_label": label,
        "visitor_city_choices": labels,
        "visitor_city_set_url": reverse("set_visitor_city"),
    }
