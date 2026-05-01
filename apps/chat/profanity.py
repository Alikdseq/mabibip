from __future__ import annotations

from better_profanity import profanity


def clean_text(text: str) -> str:
    profanity.load_censor_words()
    return profanity.censor(text or "").strip()

