from __future__ import annotations

from dataclasses import dataclass

from .context_engine import SituationContext


@dataclass(frozen=True)
class ProactiveSuggestion:
    code: str
    title: str
    detail: str
    requires_confirmation: bool = True
    auto_execute: bool = False


class ProactiveEngine:
    """Produces bounded local suggestions without executing them."""

    def suggest(
        self,
        *,
        context: SituationContext,
        memory_hits: int,
        local_failures: int,
        pending_improvements: int,
    ) -> ProactiveSuggestion | None:
        memory_hits = max(0, int(memory_hits))
        local_failures = max(0, int(local_failures))
        pending_improvements = max(0, int(pending_improvements))

        if local_failures >= 2:
            return ProactiveSuggestion(
                code="local-ai-recovery",
                title="Lokale KI prüfen",
                detail=(
                    "Mehrere lokale KI-Fehler wurden erkannt. "
                    "Scorpion kann Diagnose- und Stabilitätsschritte vorschlagen."
                ),
            )

        if context.project and memory_hits == 0 and context.domain == "technical":
            return ProactiveSuggestion(
                code="project-memory-gap",
                title="Projektkontext ergänzen",
                detail=(
                    f"Für {context.project} wurde kein passender Langzeitkontext gefunden. "
                    "Scorpion kann vorschlagen, welche Projektinformation gespeichert werden sollte."
                ),
            )

        if pending_improvements > 0 and context.domain == "technical":
            return ProactiveSuggestion(
                code="review-improvements",
                title="Verbesserungsvorschläge prüfen",
                detail=(
                    f"{pending_improvements} lokaler Verbesserungsvorschlag bzw. "
                    "Verbesserungsvorschläge warten auf deine Prüfung."
                ),
            )

        if context.priority == "quality" and context.complexity >= 0.75:
            return ProactiveSuggestion(
                code="quality-plan",
                title="Arbeitsplan anzeigen",
                detail=(
                    "Die Aufgabe ist komplex. Scorpion kann zuerst einen lokalen "
                    "Arbeitsplan anzeigen, bevor weitere Schritte ausgeführt werden."
                ),
            )

        return None
