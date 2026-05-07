"""
SEO: канонические URL и очистка query string (фаза A плана docs/seo/plan.md).

Политика пагинации каталога (A5): self-canonical для каждой страницы выдачи; page=1 в query не
включаем — каноникал совпадает с первой страницей без параметра page.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.urls import resolve

def clamp_seo_description(text: str, max_len: int = 160) -> str:
    """Укороченное meta description без обрыва mid-word где возможно."""
    t = (text or "").replace("\n", " ").strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


TRACKING_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "yclid",
        "_openstat",
        "openstat_service",
    }
)

# Только UI/аналитика каталога, на выдачу не влияют
CATALOG_NOISE_KEYS = frozenset({"entry", "quick"})

# Кабинеты, API и служебные разделы — без canonical (как и в robots.txt).
EXCLUDED_CANONICAL_PREFIXES: tuple[str, ...] = (
    "/secure-admin/",
    "/secure-erp/",
    "/accounts/",
    "/cabinet/",
    "/sto/cabinet/",
    "/billing/",
    "/api/",
    "/visitor-city/",
    "/chat/",
    "/media/",
)


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def _absolute_base_for_request(request) -> str:
    """База https://host без завершающего слэша (SITE_BASE_URL или из запроса)."""
    configured = (getattr(settings, "SITE_BASE_URL", None) or "").strip().rstrip("/")
    if configured:
        return configured
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"


def strip_tracking_query(request_get) -> list[tuple[str, str]]:
    """Пары (key, value) без трекинговых ключей; порядок ключей лексикографический."""
    items: list[tuple[str, str]] = []
    for key in sorted(set(request_get.keys())):
        if key in TRACKING_QUERY_KEYS or key in CATALOG_NOISE_KEYS:
            continue
        for val in request_get.getlist(key):
            v = (val or "").strip()
            if v:
                items.append((key, v))
    return items


def build_catalog_canonical_query(request_get) -> str:
    """
    Канонический query для /sto/: только параметры, влияющие на фильтры каталога.
    Ключи в стабильном порядке; page только для page > 1; sort без значения relevance.
    """
    p = request_get
    parts: list[tuple[str, str]] = []

    def add_single(key: str, raw: str | None) -> None:
        val = (raw or "").strip()
        if val:
            parts.append((key, val))

    add_single("q", p.get("q"))
    add_single("brand", p.get("brand"))
    add_single("service", p.get("service"))
    add_single("rating", p.get("rating"))
    add_single("district", p.get("district"))
    add_single("city", p.get("city"))

    cats = sorted({str(c).strip() for c in p.getlist("cat") if str(c).strip().isdigit()})
    for c in cats:
        parts.append(("cat", c))

    execs = sorted({str(e).strip() for e in p.getlist("exec") if str(e).strip()})
    for e in execs:
        parts.append(("exec", e))

    if _truthy(p.get("slots_today")):
        parts.append(("slots_today", "1"))
    if _truthy(p.get("slots_tomorrow")):
        parts.append(("slots_tomorrow", "1"))
    if _truthy(p.get("verified")):
        parts.append(("verified", "1"))
    if _truthy(p.get("open247")):
        parts.append(("open247", "1"))

    for amen_key in ("amen_wifi", "amen_coffee", "amen_cards", "amen_tow", "amen_legal"):
        if _truthy(p.get(amen_key)):
            parts.append((amen_key, "1"))

    sort = (p.get("sort") or "").strip() or "relevance"
    if sort != "relevance":
        parts.append(("sort", sort))

    add_single("user_lat", p.get("user_lat"))
    add_single("user_lng", p.get("user_lng"))
    try:
        r_raw = (p.get("radius_km") or "").strip()
        if r_raw:
            r_km = float(r_raw)
            if r_km > 0:
                # Стабильное представление без .0
                s = str(int(r_km)) if r_km == int(r_km) else str(r_km)
                parts.append(("radius_km", s))
    except ValueError:
        pass

    page_raw = (p.get("page") or "").strip()
    if page_raw.isdigit():
        page_n = int(page_raw)
        if page_n > 1:
            parts.append(("page", str(page_n)))

    # Уже кортежи с фиксированным порядком вставки — вторично сортируем для стабильности
    parts.sort(key=lambda kv: (kv[0], kv[1]))
    return urlencode(parts, doseq=True)


def build_canonical_url(request) -> str:
    """
    Абсолютный canonical для текущего запроса.
    Для карты «Рядом» — всегда /sto/nearby/ без гео-параметров.
    """
    path = request.path or "/"
    for pref in EXCLUDED_CANONICAL_PREFIXES:
        if path.startswith(pref):
            return ""

    base = _absolute_base_for_request(request)
    try:
        match = resolve(path)
    except Exception:
        return ""

    url_name = match.url_name
    ns = (match.namespace or "").strip()
    full_name = f"{ns}:{url_name}" if ns else url_name

    query = ""
    if full_name == "home":
        path = "/"
    elif full_name == "stations:list":
        query = build_catalog_canonical_query(request.GET)
    elif full_name == "stations:detail":
        query = ""
    elif full_name == "stations:nearby_map":
        path = reverse_path("stations:nearby_map")
        query = ""
    elif full_name == "landing:service_category":
        city = (request.GET.get("city") or "").strip()
        query = urlencode([("city", city)]) if city else ""
    elif full_name == "landing:car_brand":
        city = (request.GET.get("city") or "").strip()
        query = urlencode([("city", city)]) if city else ""
    elif full_name == "landing:service_section":
        city = (request.GET.get("city") or "").strip()
        query = urlencode([("city", city)]) if city else ""
    elif full_name == "classifieds:ads_list":
        # Дубли фильтров не индексируем: в индекс попадают только устойчивые выдачи.
        tab = (request.GET.get("tab") or "").strip()
        if tab == "part":
            query = urlencode([("tab", "part")])
        elif tab == "car":
            deal = (request.GET.get("deal") or "sale").strip().lower()
            if deal not in ("sale", "rent_car", "rent_special"):
                deal = "sale"
            query = urlencode([("tab", "car"), ("deal", deal)])
        else:
            query = ""
    elif full_name in ("classifieds:ad_detail", "classifieds:shop_detail"):
        query = ""
    elif full_name.startswith("legal:"):
        query = urlencode(strip_tracking_query(request.GET), doseq=True)
    else:
        query = urlencode(strip_tracking_query(request.GET), doseq=True)

    if path != "/" and not path.endswith("/"):
        path = path + "/"

    url = f"{base}{path}"
    if query:
        url = f"{url}?{query}"
    return url


def reverse_path(viewname: str, *, kwargs: dict | None = None) -> str:
    from django.urls import reverse

    return reverse(viewname, kwargs=kwargs or {})


def robots_txt_body(*, sitemap_absolute_url: str) -> str:
    lines = [
        "User-agent: *",
        "Disallow: /secure-admin/",
        "Disallow: /secure-erp/",
        "Disallow: /accounts/",
        "Disallow: /cabinet/",
        "Disallow: /sto/cabinet/",
        "Disallow: /billing/",
        "Disallow: /visitor-city/",
        "Disallow: /api/",
        "Disallow: /chat/",
        "",
        f"Sitemap: {sitemap_absolute_url}",
        "",
    ]
    return "\n".join(lines)
