from __future__ import annotations

import time
from dataclasses import dataclass

from .context_engine import analyze_context
from .model_router import ModelRouter, TaskKind


@dataclass(frozen=True)
class AgentStageResult:
    role: str
    model: str
    output: str


@dataclass(frozen=True)
class AgentTeamResult:
    objective: str
    stages: tuple[AgentStageResult, ...]

    @property
    def final_output(self) -> str:
        return self.stages[-1].output if self.stages else ""


class LocalAgentTeam:
    """Sequential local agent team for Ruflo-coordinated Scorpion work.

    All roles reuse the existing Ollama backend. This avoids loading one large
    model per role and never grants agents permission to apply updates/files.
    """

    ROLE_INSTRUCTIONS = (
        (
            "coder",
            "Erstelle einen konkreten technischen Lösungsentwurf. "
            "Nenne betroffene Komponenten, Risiken und Tests. Ändere nichts selbst.",
        ),
        (
            "tester",
            "Prüfe den vorgeschlagenen Lösungsentwurf kritisch. "
            "Suche Regressionen, fehlende Tests und unklare Annahmen. Ändere nichts selbst.",
        ),
        (
            "production-validator",
            "Fasse die geprüfte Lösung als sicheren Freigabevorschlag zusammen. "
            "Markiere Blocker und sage klar, was vor einer Installation bestätigt werden muss. "
            "Wende nichts automatisch an.",
        ),
    )

    def __init__(self, local_ai, model_router: ModelRouter):
        self.local_ai = local_ai
        self.model_router = model_router

    def run(self, objective: str) -> AgentTeamResult:
        objective = " ".join(str(objective).strip().split())
        if not objective:
            raise ValueError("Agenten-Team braucht ein konkretes Ziel.")

        context = analyze_context(objective)
        prior = ""
        stages: list[AgentStageResult] = []

        for role, instruction in self.ROLE_INSTRUCTIONS:
            priority = "quality" if role != "tester" else "balanced"
            route = self.model_router.route(
                TaskKind.REASONING,
                complexity=0.9,
                priority=priority,
            )
            model = route.model
            if not model:
                raise RuntimeError("Kein lokales Modell für Ruflo-Agenten verfügbar.")

            prompt = (
                f"Du arbeitest als Scorpion-{role}.\n"
                f"Ziel: {objective}\n"
                f"Aufgabe: {instruction}\n"
            )
            if prior:
                prompt += (
                    "\nVorherige Agenten-Ergebnisse:\n"
                    + prior[-5000:]
                    + "\n"
                )
            prompt += (
                "\nArbeite auf Hochdeutsch. Bleibe lokal. "
                "Keine Dateiänderung, kein Cloud-Aufruf und keine Update-Installation."
            )

            started = time.monotonic()
            success = False
            try:
                output = self.local_ai.respond(
                    prompt,
                    history=(),
                    model=model,
                    context=context,
                    memory_context=None,
                )
                success = bool(str(output).strip())
            finally:
                try:
                    self.model_router.record_result(
                        route,
                        latency_ms=(time.monotonic() - started) * 1000.0,
                        success=success,
                    )
                except Exception:
                    pass

            output = str(output).strip()
            stages.append(AgentStageResult(role=role, model=model, output=output))
            prior += f"\n[{role} · {model}]\n{output}\n"

        return AgentTeamResult(objective=objective, stages=tuple(stages))
