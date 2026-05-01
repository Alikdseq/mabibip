"""Нормализация текста для поисковых фраз и запросов водителей."""

from __future__ import annotations

import re
from collections.abc import Iterable

# «Женский» / бытовой контент остаётся в фразе; убираем только шумовые слова.
_STOP_WORDS = frozenset(
    {
        "в",
        "во",
        "на",
        "по",
        "с",
        "со",
        "у",
        "к",
        "ко",
        "от",
        "до",
        "из",
        "за",
        "для",
        "при",
        "и",
        "или",
        "а",
        "но",
        "же",
        "ли",
        "бы",
        "машина",
        "авто",
        "автомобиль",
        "машину",
        "машины",
        "меня",
        "мне",
        "моего",
        "мой",
        "моя",
        "что",
        "это",
        "как",
        "то",
        "там",
        "тут",
        "уже",
        "ещё",
        "еще",
    }
)

# Бытовые формы → корни/словоформы как в словаре фраз (списокзапросов.txt).
_DRIVER_TOKEN_ALIASES: dict[str, frozenset[str]] = {
    "стучит": frozenset({"стук", "стука", "стуке"}),
    "стучат": frozenset({"стук"}),
    "скрипит": frozenset({"скрип", "скрипа", "скрипе"}),
    "скрипят": frozenset({"скрип"}),
    "троит": frozenset({"троит", "трою", "троение"}),
    "троят": frozenset({"троит"}),
    "дымит": frozenset({"дым", "дымит"}),
    "глохнет": frozenset({"глох", "глохнет"}),
    "глохнут": frozenset({"глох"}),
    "жрет": frozenset({"жрет", "жрёт", "жрать"}),
    "жрёт": frozenset({"жрет"}),
    "пинается": frozenset({"пина", "пин"}),
    "пинаются": frozenset({"пина"}),
    "буксует": frozenset({"букс"}),
    "дергается": frozenset({"дерга", "дерг"}),
    "дёргается": frozenset({"дерга"}),
    "плавают": frozenset({"плавают", "плава"}),
    "щелкает": frozenset({"щелка", "щёлка"}),
    "щёлкает": frozenset({"щелка"}),
    "моргают": frozenset({"морга"}),
    "заводится": frozenset({"завод", "заводится"}),
    "заводиться": frozenset({"завод"}),
    "схватывает": frozenset({"схват"}),
    "крутит": frozenset({"крут"}),
    "дует": frozenset({"дует", "дуть"}),
    "потеет": frozenset({"поте", "пот"}),
    "запотевают": frozenset({"запотев"}),
    "чихает": frozenset({"чих"}),
}


def normalize_search_text(text: str) -> str:
    """Нижний регистр, пунктуация → пробелы, стоп-слова убраны, пробелы схлопнуты."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s\-]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    parts = [p for p in t.split() if p and p not in _STOP_WORDS]
    out = " ".join(parts)
    return out if out else t


def query_tokens(q_normalized: str, q_raw: str) -> list[str]:
    """Значимые токены запроса (и из нормализованной строки, и из сырой, если всё вырезали)."""
    raw = (q_raw or "").lower().strip()
    raw = re.sub(r"[^\w\s\-]", " ", raw, flags=re.UNICODE)
    raw = re.sub(r"\s+", " ", raw).strip()
    from_norm = [p for p in (q_normalized or "").split() if len(p) >= 1]
    if from_norm:
        return from_norm
    return [p for p in raw.split() if len(p) >= 1 and p not in _STOP_WORDS]


def expand_driver_query_tokens(tokens: Iterable[str]) -> set[str]:
    """
    Расширение токенов под «живую» речь: окончания глаголов, алиасы, общие корни
    (двигатель ↔ двигателе в словаре).
    """
    out: set[str] = set()
    for t in tokens:
        if not t:
            continue
        low = t.lower().strip()
        if len(low) < 1:
            continue
        out.add(low)
        aliases = _DRIVER_TOKEN_ALIASES.get(low)
        if aliases:
            out.update(aliases)
        # 3 л. наст.: скрипит → скрип, стучит → стуч
        if len(low) >= 5:
            if low.endswith(("ится", "ает", "яет", "ует", "ишь")):
                out.add(low[:-3])
                out.add(low[:-2])
            elif low.endswith(("ает", "яет")):
                out.add(low[:-2])
        if len(low) >= 4 and low.endswith("ит"):
            out.add(low[:-2])
            if len(low) >= 5:
                out.add(low[:-3])
        if len(low) >= 4 and low.endswith(("ет", "ат", "ят", "ут", "ют")):
            out.add(low[:-2])
        if low.startswith("двигат"):
            out.update(("двигатель", "двигателе", "двигателя", "двигателем", "двс"))
        if low.startswith("скрип"):
            out.update(("скрип", "скрипит", "скрипят"))
        if low.startswith("стуч") or low.startswith("стук"):
            out.update(("стук", "стука", "стуке", "стучит"))
        if low.startswith("тро"):
            out.add("троит")
    return {x for x in out if len(x) >= 2}
