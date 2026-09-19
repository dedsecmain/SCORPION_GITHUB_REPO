from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .response_style import ResponseTone, classify_response_tone


_TECHNICAL_MARKERS = {
    "github", "repo", "repository", "commit", "branch", "workflow", "release",
    "update", "code", "python", "terminal", "debug", "bug", "fehler", "server",
    "ollama", "unreal", "unity", "api", "modell", "model", "hud", "scorpion",
}
_COMPLEX_MARKERS = {
    "analysiere", "begründe", "architektur", "strategie", "vergleich", "debug",
    "implementiere", "integriere", "recherchiere", "prüfe", "optimiere",
}
_LANGUAGE_OVERRIDES = (
    (("auf englisch", "in english", "english please"), "en"),
    (("auf portugiesisch", "portugiesisch", "em português", "português"), "pt-BR"),
    (("auf italienisch", "italienisch", "in italiano"), "it"),
    (("auf französisch", "französisch", "en français"), "fr"),
)


@dataclass(frozen=True)
class SituationContext:
    response_language: str
    domain: str
    project: str | None
    priority: str
    complexity: float
    serious: bool
    tone: ResponseTone

    @property
    def label(self) -> str:
        project = f" · {self.project.upper()}" if self.project else ""
        return f"{self.domain.upper()}{project} · {self.priority.upper()}"


def _response_language(text: str) -> str:
    lowered = text.casefold()
    for markers, language in _LANGUAGE_OVERRIDES:
        if any(marker in lowered for marker in markers):
            return language
    return "de-DE"


def _project(text: str, history: Iterable[dict[str, str]]) -> str | None:
    combined = " ".join(
        [text]
        + [
            str(item.get("content", ""))
            for item in list(history)[-4:]
            if isinstance(item, dict)
        ]
    ).casefold()
    if any(marker in combined for marker in ("scorpion", "mk23", "mk47", "mk50", "mk74")):
        return "scorpion"
    if any(marker in combined for marker in ("playbox", "unreal engine", "unrealengine", "minute heist")):
        return "playbox"
    return None


def _complexity(text: str, technical: bool) -> float:
    lowered = text.casefold()
    score = min(0.55, len(text) / 1400.0)
    if technical:
        score += 0.18
    if any(marker in lowered for marker in _COMPLEX_MARKERS):
        score += 0.32
    if "?" in text and len(text) > 220:
        score += 0.08
    return max(0.0, min(1.0, score))


def analyze_context(
    text: str,
    history: Iterable[dict[str, str]] = (),
) -> SituationContext:
    normalized = " ".join(str(text or "").split())
    lowered = normalized.casefold()
    tone = classify_response_tone(normalized)
    serious = tone is ResponseTone.SERIOUS
    technical = any(marker in lowered for marker in _TECHNICAL_MARKERS)
    domain = "sensitive" if serious else ("technical" if technical else "general")
    project = _project(normalized, history)
    complexity = _complexity(normalized, technical)
    priority = "quality" if serious or technical or complexity >= 0.65 else "speed"
    return SituationContext(
        response_language=_response_language(normalized),
        domain=domain,
        project=project,
        priority=priority,
        complexity=complexity,
        serious=serious,
        tone=tone,
    )


def tokenize_for_relevance(value: str) -> set[str]:
    words = re.findall(r"[\wäöüßéèàçãõáíóú]+", str(value).casefold(), flags=re.UNICODE)
    stop = {
        "der", "die", "das", "den", "dem", "ein", "eine", "einer", "und", "oder",
        "ist", "sind", "war", "was", "wie", "mit", "für", "von", "im", "in", "auf",
        "zu", "ich", "du", "wir", "bitte", "beim", "beim", "beim", "the", "and",
    }
    return {word for word in words if len(word) >= 3 and word not in stop}
