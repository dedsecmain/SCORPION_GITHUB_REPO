from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class WakeMatch:
    matched_text: str
    normalized_alias: str
    trailing_text: str


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return "".join(ch for ch in normalized if ch.isalnum())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    previous = list(range(len(a) + 1))
    for i, bch in enumerate(b, start=1):
        current = [i]
        for j, ach in enumerate(a, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (ach != bch),
                )
            )
        previous = current
    return previous[-1]


class WakeMatcher:
    def __init__(
        self,
        wake_word: str,
        aliases: set[str] | None = None,
        *,
        max_edit_distance: int = 2,
        min_fuzzy_length: int = 6,
    ):
        canonical = _normalize_token(wake_word)
        self.canonical = canonical
        default_aliases = {canonical, "skorpion", "scorpian"}
        supplied = aliases if aliases is not None else default_aliases
        self.aliases = {_normalize_token(item) for item in supplied if _normalize_token(item)} | {canonical}
        self.max_edit_distance = max(0, int(max_edit_distance))
        self.min_fuzzy_length = max(1, int(min_fuzzy_length))

    def match(self, text: str) -> WakeMatch | None:
        if not isinstance(text, str) or not text.strip():
            return None
        for token in re.finditer(r"[^\W_]+", text, flags=re.UNICODE):
            raw = token.group(0)
            normalized = _normalize_token(raw)
            accepted_alias: str | None = None
            if normalized in self.aliases:
                accepted_alias = normalized
            elif (
                len(normalized) >= self.min_fuzzy_length
                and abs(len(normalized) - len(self.canonical)) <= self.max_edit_distance
                and _levenshtein(normalized, self.canonical) <= self.max_edit_distance
            ):
                accepted_alias = normalized
            if accepted_alias is None:
                continue

            trailing = text[token.end() :]
            trailing = re.sub(r"^[\s,.:;!?\-–—]+", "", trailing).strip()
            return WakeMatch(raw, accepted_alias, trailing)
        return None
