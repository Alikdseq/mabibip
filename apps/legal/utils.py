"""Безопасный рендер Markdown для публичных юридических текстов (XSS — см. документ 07, B.4)."""

from __future__ import annotations

import bleach
import markdown


# Разрешены только безопасные теги; ссылки — только http(s).
_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "u",
        "h1",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "blockquote",
        "code",
        "pre",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "a",
    }
)
_ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def render_legal_markdown(text: str) -> str:
    # Без 'extra': меньше произвольного HTML от парсера; таблицы и код — по необходимости в текстах.
    raw_html = markdown.markdown(
        text,
        extensions=["nl2br", "tables", "fenced_code"],
        output_format="html",
    )
    return bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
