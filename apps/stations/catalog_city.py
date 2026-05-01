"""Фильтр станций по городу посетителя (шапка сайта / GET city)."""

from __future__ import annotations

from django.db.models import Q


def filter_queryset_by_visitor_city(qs, city_label: str | None):
    """
    Показываем станции, у которых район из справочника совпадает с городом посетителя,
    либо район не выбран, но адрес содержит название этого города (частый случай после заполнения профиля).
    """
    ec = (city_label or "").strip()
    if not ec:
        return qs
    return (
        qs.filter(
            Q(district__city_label__iexact=ec)
            | (Q(district__isnull=True) & Q(address__icontains=ec)),
        )
        .distinct()
    )
