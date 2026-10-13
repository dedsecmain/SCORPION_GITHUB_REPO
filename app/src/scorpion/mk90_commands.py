"""Deterministic MK90 browser command recognition, before any LLM call."""
from __future__ import annotations

import re


_HOST = re.compile(
    r"(?i)^(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)\.[a-z]{2,}"
    r"(?::\d+)?(?:[/?#][^\s]*)?$"
)
_PREFIXES = (
    "lies webseite ", "lies die webseite ", "zeige webseite ",
    "öffne webseite ", "öffne die webseite ",
    "oeffne webseite ", "oeffne die webseite ",
)


def requested_browser_url(text: str) -> str | None:
    """Only explicit website commands or a standalone URL/host.

    The actual trust decision stays in require_public_https_url and the
    approval callback. Never forward a candidate URL to Ollama first.
    """
    value = str(text or "").strip()
    if not value or any(ch.isspace() for ch in value if ch not in " "):
        return None
    candidate = value
    lower = value.casefold()
    for prefix in _PREFIXES:
        if lower.startswith(prefix):
            candidate = value[len(prefix):].strip()
            break
    else:
        # Plain prose containing links is *not* a browsing instruction.
        if " " in value:
            return None

    if " " in candidate or not candidate:
        return None
    if candidate.lower().startswith(("https://", "http://")):
        return candidate
    if _HOST.fullmatch(candidate):
        return "https://" + candidate
    return None
