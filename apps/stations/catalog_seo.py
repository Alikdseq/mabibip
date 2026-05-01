"""Title и meta description для страницы каталога /sto/ (фаза B SEO)."""

from __future__ import annotations

from apps.core.seo import clamp_seo_description


def build_catalog_page_seo(
    *,
    meta: dict,
    visitor_city_label: str | None,
    category_names: list[str],
) -> dict[str, str]:
    """
    Возвращает ключи seo_og_title, seo_meta_description для шаблона и Open Graph.
    """
    city = (meta.get("catalog_effective_city") or "").strip() or (visitor_city_label or "").strip()
    q = (meta.get("catalog_q") or "").strip()
    brand_name = ""
    bo = meta.get("catalog_brand_obj")
    if isinstance(bo, dict):
        brand_name = (bo.get("name") or "").strip()

    cats_sorted = sorted({(n or "").strip() for n in category_names if (n or "").strip()})
    cat_hint = ""
    if cats_sorted:
        if len(cats_sorted) == 1:
            cat_hint = cats_sorted[0]
        else:
            cat_hint = f"{cats_sorted[0]} и ещё {len(cats_sorted) - 1}"

    fragments: list[str] = []
    if city:
        fragments.append(f"СТО и мастера в {city}")
    else:
        fragments.append("СТО и мастера")
    if brand_name:
        fragments.append(brand_name)
    if cat_hint:
        fragments.append(cat_hint)
    if q and len(q) <= 40:
        fragments.append(f"поиск «{q}»")

    title_core = " · ".join(fragments)
    title = f"{title_core} — МаБибип"
    if len(title) > 72:
        title = f"{' · '.join(fragments[:3])} — МаБибип"
    if len(title) > 72:
        title = "Мастера и сервисы — МаБибип"

    # Description: уникальный при наличии города / марки / услуг / запроса
    desc_parts: list[str] = []
    if city:
        desc_parts.append(f"Исполнители в {city}: СТО и частные мастера.")
    else:
        desc_parts.append("Мастера, автосервисы и частные исполнители.")
    if brand_name:
        desc_parts.append(f"Марка: {brand_name}.")
    if cat_hint:
        desc_parts.append(f"Услуги: {cat_hint}.")
    if q:
        desc_parts.append(f"Поиск: «{q[:50]}».")
    desc_parts.append("Отзывы, цены, запись онлайн.")
    description = clamp_seo_description(" ".join(desc_parts))

    return {
        "catalog_seo_title": title,
        "seo_og_title": title,
        "seo_meta_description": description,
    }
