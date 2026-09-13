from __future__ import annotations

import re


def extract_after_wake_phrase(text: str, wake_word: str = "scorpion") -> str | None:
    """Return speech after the wake phrase when it starts the utterance."""
    normalized = text.strip()
    pattern = rf"^(?:hey\s+)?{re.escape(wake_word)}\b[\s,.:;!?-]*"
    match = re.match(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return normalized[match.end():].strip()


def extract_after_wake_phrase_anywhere(text: str, wake_word: str = "scorpion") -> str | None:
    """Return text after the first wake phrase in a longer transcript."""
    normalized = text.strip()
    pattern = rf"(?:\bhey\s+)?\b{re.escape(wake_word)}\b[\s,.:;!?-]*"
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return normalized[match.end():].strip()
