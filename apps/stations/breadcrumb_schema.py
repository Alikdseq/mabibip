"""JSON-LD BreadcrumbList для SEO-лендингов."""

from __future__ import annotations

import json

from django.urls import reverse


def breadcrumb_json_ld(*, request, items: list[tuple[str, str]]) -> str:
    """
    items: list of (name, absolute_or_relative_url).
    URL будет приведён к абсолютному, если передан request.
    """

    def _abs(url: str) -> str:
        if not url:
            return ""
        if request and not url.startswith("http"):
            return request.build_absolute_uri(url)
        return url

    list_items = []
    pos = 0
    for name, url in items:
        pos += 1
        u = _abs(url)
        if not u and request:
            u = request.build_absolute_uri(reverse("home"))
        list_items.append({"@type": "ListItem", "position": pos, "name": name, "item": u})

    doc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": list_items}
    return json.dumps(doc, ensure_ascii=False)

