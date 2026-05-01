"""Умные подсказки: словарь фраз + токены «живой» речи + триграммы (PostgreSQL)."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from django.db import connection
from django.db.models import Q
from django.urls import reverse

from .models import ServiceCategory, ServiceSearchPhrase, ServiceSection, ServiceStation
from .search_text import (
    expand_driver_query_tokens,
    normalize_search_text,
    query_tokens,
)


def _sequence_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _token_pair_score(qw: str, bw: str) -> float:
    """Сходство одного слова запроса и слова из фразы словаря."""
    if not qw or not bw:
        return 0.0
    qw, bw = qw.lower(), bw.lower()
    if qw == bw:
        return 1.0
    if len(qw) >= 2 and len(bw) >= 2 and (qw in bw or bw in qw):
        return 0.94
    r = _sequence_ratio(qw, bw)
    if r >= 0.84:
        return 0.9
    if r >= 0.74:
        return 0.78
    if r >= 0.58 and min(len(qw), len(bw)) >= 4:
        return 0.7
    n = min(len(qw), len(bw))
    if n >= 4 and qw[:4] == bw[:4]:
        return 0.72
    # «стучит» ↔ «стук», «скрипит» ↔ «скрип»: общий корень 3+ букв
    if len(qw) >= 3 and len(bw) >= 3 and qw[:3] == bw[:3] and abs(len(qw) - len(bw)) <= 5:
        return max(0.76, r)
    return 0.0


def _phrase_bag(phrase: ServiceSearchPhrase) -> set[str]:
    """Все значимые куски фразы для матчинга."""
    bag: set[str] = set()
    for part in (phrase.phrase_normalized or "").split():
        p = part.strip(".,;:!?«»\"'()")
        if len(p) >= 2:
            bag.add(p.lower())
    for part in (phrase.phrase or "").lower().split():
        p = part.strip(".,;:!?«»\"'()")
        if len(p) >= 2:
            bag.add(p)
    return bag


def _score_phrase_against_query(phrase: ServiceSearchPhrase, q_words: list[str], q_norm: str, q_raw: str) -> float:
    """Чем выше — тем ближе формулировка пользователя к строке словаря."""
    if not q_words:
        return 0.0
    bag = _phrase_bag(phrase)
    if not bag:
        return 0.0
    cov = 0.0
    for qw in q_words:
        if len(qw) < 1:
            continue
        best = max((_token_pair_score(qw, bw) for bw in bag), default=0.0)
        cov += best
    base = (cov / len(q_words)) * 95.0
    pr = (phrase.phrase or "").lower()
    qr = (q_raw or "").lower().strip()
    if qr and qr in pr:
        base += 55.0
    if q_norm and q_norm == phrase.phrase_normalized:
        base += 70.0
    elif q_norm and q_norm in (phrase.phrase_normalized or ""):
        base += 40.0
    elif (phrase.phrase_normalized or "") in q_norm:
        base += 35.0
    base += float(phrase.weight) * 2.0
    return base


def _collect_phrase_candidates_postgres(q_norm: str, q_raw: str, expanded: set[str]) -> list[ServiceSearchPhrase]:
    from django.contrib.postgres.search import TrigramSimilarity

    base = ServiceSearchPhrase.objects.select_related("category")
    seen: dict[int, ServiceSearchPhrase] = {}

    if len(q_norm) >= 2:
        for row in (
            base.annotate(sim=TrigramSimilarity("phrase_normalized", q_norm))
            .filter(sim__gt=0.07)
            .order_by("-sim")[:40]
        ):
            seen[row.pk] = row

    q_obj = Q()
    n_terms = 0
    for t in sorted(expanded, key=len, reverse=True):
        if len(t) < 2:
            continue
        q_obj |= Q(phrase_normalized__icontains=t) | Q(phrase__icontains=t)
        n_terms += 1
        if n_terms >= 18:
            break
    if n_terms > 0:
        for row in base.filter(q_obj).distinct()[:180]:
            seen[row.pk] = row

    return list(seen.values())


def _collect_phrase_candidates_sqlite(q_norm: str, expanded: set[str]) -> list[ServiceSearchPhrase]:
    base = ServiceSearchPhrase.objects.select_related("category")
    seen: dict[int, ServiceSearchPhrase] = {}
    q_obj = Q()
    n_terms = 0
    for t in sorted(expanded, key=len, reverse=True):
        if len(t) < 2:
            continue
        q_obj |= Q(phrase_normalized__icontains=t) | Q(phrase__icontains=t)
        n_terms += 1
        if n_terms >= 18:
            break
    if n_terms > 0:
        for row in base.filter(q_obj).distinct()[:180]:
            seen[row.pk] = row
    return list(seen.values())


def _rank_phrases(
    candidates: list[ServiceSearchPhrase],
    q_words: list[str],
    q_norm: str,
    q_raw: str,
) -> list[tuple[ServiceSearchPhrase, float, str]]:
    scored: list[tuple[ServiceSearchPhrase, float, str]] = []
    for ph in candidates:
        s = _score_phrase_against_query(ph, q_words, q_norm, q_raw)
        if s < 22.0:
            continue
        scored.append((ph, s, ph.phrase))
    scored.sort(key=lambda x: -x[1])
    return scored[:48]


def build_search_suggestions(
    *,
    q_raw: str,
    visible_stations,
    service_limit: int = 5,
    section_limit: int = 4,
    master_limit: int = 3,
    station_limit: int = 3,
    include_stations: bool = True,
    include_masters: bool = True,
) -> dict[str, Any]:
    q_strip = (q_raw or "").strip()
    q_norm = normalize_search_text(q_strip)
    q_words = query_tokens(q_norm, q_strip)
    expanded = expand_driver_query_tokens(q_words)
    services_accum: dict[int, dict[str, Any]] = {}

    if len(q_strip) >= 1 and q_words:
        if connection.vendor == "postgresql":
            candidates = _collect_phrase_candidates_postgres(q_norm, q_strip, expanded)
        else:
            candidates = _collect_phrase_candidates_sqlite(q_norm, expanded)
        phrase_hits = _rank_phrases(candidates, q_words, q_norm, q_strip)

        for row, score, matched_phrase in phrase_hits:
            cid = row.category_id
            cur = services_accum.get(cid)
            payload = {"score": score, "category": row.category, "matched_query": matched_phrase}
            if cur is None or score > cur["score"]:
                services_accum[cid] = payload

        for cat, score in _category_name_hits(q_strip, q_norm):
            cid = cat.pk
            cur = services_accum.get(cid)
            if cur is None or score > cur["score"]:
                services_accum[cid] = {"score": score, "category": cat, "matched_query": None}

    ranked_services = sorted(services_accum.values(), key=lambda x: -x["score"])
    top_services = ranked_services[:service_limit]

    ambiguous_hint: str | None = None
    if len(ranked_services) >= 2:
        s0 = ranked_services[0]["score"]
        s1 = ranked_services[1]["score"]
        if s0 > 0 and (s0 - s1) <= 14.0:
            take = min(3, len(ranked_services))
            names = [ranked_services[i]["category"].name for i in range(take)]
            ambiguous_hint = "Возможно, вы ищете: " + ", ".join(names)

    results: list[dict[str, Any]] = []
    services_payload: list[dict[str, Any]] = []
    sections_payload: list[dict[str, Any]] = []
    masters_payload: list[dict[str, Any]] = []

    for item in top_services:
        cat = item["category"]
        match_label = item["matched_query"]
        hint = "Категория услуг"
        if match_label:
            hint = f"По запросу «{match_label}»"
        landing_url = reverse("landing:service_category", kwargs={"slug": cat.slug})
        row = {
            "type": "category",
            "id": cat.pk,
            "slug": cat.slug,
            "label": cat.name,
            "hint": hint,
            "url": landing_url,
            "matched_query": match_label,
            "category_name": cat.name,
        }
        services_payload.append(row)
        results.append(row)

    if len(q_strip) >= 1 and section_limit > 0:
        secs = list(ServiceSection.objects.filter(name__icontains=q_strip).order_by("sort_order", "name")[:section_limit])
        for sec in secs:
            row = {
                "type": "section",
                "id": sec.pk,
                "slug": sec.slug,
                "label": sec.name,
                "hint": "Раздел услуг",
                "url": reverse("landing:service_section", kwargs={"slug": sec.slug}),
                "matched_query": None,
                "category_name": None,
            }
            sections_payload.append(row)
            results.append(row)

    if include_masters and master_limit > 0 and len(q_strip) >= 1:
        masters = list(
            visible_stations.filter(parent_station__isnull=False).filter(
                Q(name__icontains=q_strip) | Q(tagline__icontains=q_strip)
            ).select_related("parent_station").order_by("name")[:master_limit]
        )
        for m in masters:
            hint_parts = ["Мастер"]
            if m.parent_station_id and getattr(m, "parent_station", None):
                hint_parts.append(f"из {m.parent_station.name}")
            if m.tagline:
                hint_parts.append(m.tagline[:80])
            row = {
                "type": "master",
                "id": m.pk,
                "slug": m.slug,
                "label": m.name,
                "hint": " · ".join([p for p in hint_parts if p]),
                "url": reverse("stations:detail", kwargs={"slug": m.slug}),
                "matched_query": None,
                "category_name": None,
            }
            masters_payload.append(row)
            results.append(row)

    stations: list[ServiceStation] = []
    if include_stations and len(q_strip) >= 2:
        stations = list(
            visible_stations.filter(Q(name__icontains=q_strip) | Q(address__icontains=q_strip)).order_by(
                "name"
            )[:station_limit]
        )
        have_ids = {s.pk for s in stations}
        extra_qs = (
            visible_stations.filter(categories__name__icontains=q_strip)
            .exclude(pk__in=have_ids)
            .order_by("name")[: max(0, station_limit - len(stations))]
        )
        stations.extend(list(extra_qs))

    for s in stations:
        results.append(
            {
                "type": "sto",
                "id": s.pk,
                "slug": s.slug,
                "label": s.name,
                "hint": (s.address or "")[:120],
                "url": reverse("stations:detail", kwargs={"slug": s.slug}),
                "matched_query": None,
                "category_name": None,
            }
        )

    stations_payload = [r for r in results if r["type"] == "sto"]

    return {
        "results": results,
        "services": services_payload,
        "sections": sections_payload,
        "masters": masters_payload,
        "stations": stations_payload,
        "ambiguous_hint": ambiguous_hint,
    }


def _category_name_hits(q_raw: str, q_norm: str) -> list[tuple[ServiceCategory, float]]:
    q_strip = (q_raw or "").strip()
    out: list[tuple[ServiceCategory, float]] = []
    if len(q_strip) < 1:
        return out
    q_low = q_strip.lower()
    for cat in ServiceCategory.objects.all():
        name_l = cat.name.lower()
        boost = 0.0
        if name_l == q_low:
            boost = 72.0
        elif len(q_low) == 1 and name_l.startswith(q_low):
            boost = 48.0
        elif q_low in name_l:
            boost = 52.0
        elif q_norm and q_norm in normalize_search_text(cat.name):
            boost = 44.0
        if boost > 0:
            out.append((cat, boost))
    return out
