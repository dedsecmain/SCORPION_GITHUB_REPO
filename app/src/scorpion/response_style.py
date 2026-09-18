from __future__ import annotations

from enum import Enum


class ResponseTone(str, Enum):
    SIGNATURE = "SIGNATURE"
    FOCUSED = "FOCUSED"
    SERIOUS = "SERIOUS"


_SERIOUS_MARKERS = (
    "starke schmerzen", "schmerzen", "notfall", "unfall", "arzt", "krankenhaus",
    "sterben", "tod", "suizid", "selbstmord", "panik", "bedroh", "gefährlich",
    "polizei", "strafe", "anzeige", "missbrauch", "verletzt",
)

_FOCUSED_MARKERS = (
    "github", "update", "fehler", "bug", "code", "terminal", "datei", "projekt",
    "install", "release", "commit", "branch", "test", "prüfe", "analysiere",
    "unreal", "server", "repo", "workflow", "debug",
)


def classify_response_tone(text: str) -> ResponseTone:
    lowered = (text or "").casefold()
    if any(marker in lowered for marker in _SERIOUS_MARKERS):
        return ResponseTone.SERIOUS
    if any(marker in lowered for marker in _FOCUSED_MARKERS):
        return ResponseTone.FOCUSED
    return ResponseTone.SIGNATURE


def style_guidance(tone: ResponseTone) -> str:
    if tone is ResponseTone.SERIOUS:
        return (
            "Antworte ruhig, klar und respektvoll; keine Witze, kein freches Auftreten und "
            "keine unnötigen Sprüche. Priorisiere Sicherheit, Präzision und konkrete nächste Schritte."
        )
    if tone is ResponseTone.FOCUSED:
        return (
            "Arbeite präzise, souverän und direkt, mit wenig Smalltalk und kurzer passender Persönlichkeit, "
            "aber technische Fakten, Status und nächste Schritte stehen klar im Vordergrund."
        )
    return (
        "Klinge selbstbewusst, locker, spielerisch und gelegentlich leicht frech. "
        "Nutze passenden modernen Sprachfluss, ohne künstlich zu wirken oder jeden Satz mit Slang zu überladen. "
        "Ein kurzer Spruch ist okay, wenn er natürlich passt."
    )
