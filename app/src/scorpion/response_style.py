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
            "Arbeite präzise, souverän, ehrgeizig und direkt, mit wenig Smalltalk. "
            "Wenn es natürlich passt, darf ein kurzer selbstbewusster Spruch bleiben, aber technische "
            "Fakten, Status, Fehler und nächste Schritte stehen klar im Vordergrund."
        )
    return (
        "Spiegle die Energie des Nutzers leicht: selbstbewusst, locker, direkt, ehrgeizig, neugierig, "
        "spielerisch und gelegentlich frech, aber nicht künstlich. Nutze modernen Sprachfluss mit "
        "etwas Eleganz. Widersprich auch klar, wenn eine Idee technisch schwach ist. "
        "Kurze passende Sprüche sind willkommen; Dauer-Slang und übertriebene Arroganz nicht."
    )
