from __future__ import annotations

import time
from dataclasses import dataclass

from .context_engine import analyze_context
from .model_router import ModelRoute, ModelRouter, TaskKind


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

    def __init__(self, local_ai, model_router: ModelRouter, *, progress_callback=None):
        self.local_ai = local_ai
        self.model_router = model_router
        self.progress_callback = progress_callback

    def _progress(self, role: str, state: str, model: str) -> None:
        callback = self.progress_callback
        if not callable(callback):
            return
        try:
            callback(role, state, model)
        except Exception:
            pass

    def run(self, objective: str, *, deep: bool = False) -> AgentTeamResult:
        objective = " ".join(str(objective).strip().split())
        if not objective:
            raise ValueError("Agenten-Team braucht ein konkretes Ziel.")

        context = analyze_context(objective)
        prior = ""
        stages: list[AgentStageResult] = []

        # Ruflo agents deliberately prefer the small Qwen backend and ignore
        # historical health penalties caused by earlier timeout-heavy builds.
        # This prevents the agent path from silently falling back to Gemma.
        installed = set(getattr(self.model_router, "installed_models", set()) or set())
        model = next(
            (
                candidate
                for candidate in ("qwen3.5:4b", "qwen3:4b", "qwen3:8b", "gemma3:4b")
                if candidate in installed
            ),
            None,
        )
        if model is None:
            fallback = self.model_router.route(
                TaskKind.REASONING,
                complexity=0.65,
                priority="speed",
            )
            model = fallback.model
        if not model:
            raise RuntimeError("Kein lokales Modell für Ruflo-Agenten verfügbar.")
        route = ModelRoute(
            provider="local",
            model=model,
            requires_approval=False,
            reason="Ruflo-Agentenpfad · Qwen-first · kompakter Kontext",
        )

        if not deep:
            role = "fast-team"
            self._progress(role, "start", model)
            prompt = (
                "Du bist Scorpions schnelles lokales Entwicklungs-Team in einer einzigen Runde.\n"
                f"Ziel: {objective}\n"
                "Erledige intern drei Rollen kompakt: 1) Coder: Lösung, "
                "2) Tester: wichtigste Risiken/Tests, 3) Validator: sichere Empfehlung.\n"
                "Antworte kurz und konkret auf Hochdeutsch. Maximal etwa 350 Wörter. "
                "Keine Dateiänderung, kein Cloud-Aufruf und keine Update-Installation."
            )
            started = time.monotonic()
            success = False
            try:
                output = self.local_ai.respond_agent(
                    prompt,
                    model=model,
                    system_prompt=(
                        "Du bist Scorpions lokales Fast-Team. "
                        "Liefere nur Lösung, wichtigste Tests und Freigabehinweis."
                    ),
                    options={
                        "temperature": 0.15,
                        "num_ctx": 1536,
                        "num_predict": 180,
                    },
                    request_timeout=75.0,
                    retry_attempts=0,
                    keep_alive="15m",
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
            self._progress(role, "done", model)
            return AgentTeamResult(objective=objective, stages=tuple(stages))

        for role, instruction in self.ROLE_INSTRUCTIONS:
            self._progress(role, "start", model)
            prompt = (
                f"Du arbeitest als Scorpion-{role}.\n"
                f"Ziel: {objective}\n"
                f"Aufgabe: {instruction}\n"
            )
            if prior:
                prompt += (
                    "\nVorherige Agenten-Ergebnisse:\n"
                    + prior[-2600:]
                    + "\n"
                )
            prompt += (
                "\nArbeite auf Hochdeutsch. Bleibe lokal. "
                "Keine Dateiänderung, kein Cloud-Aufruf und keine Update-Installation."
            )

            started = time.monotonic()
            success = False
            deep_limits = {
                "coder": {"num_ctx": 1536, "num_predict": 140, "temperature": 0.15},
                "tester": {"num_ctx": 1536, "num_predict": 110, "temperature": 0.10},
                "production-validator": {"num_ctx": 1536, "num_predict": 90, "temperature": 0.10},
            }
            try:
                output = self.local_ai.respond_agent(
                    prompt,
                    model=model,
                    system_prompt=(
                        f"Du bist Scorpions lokaler {role}. "
                        "Bleibe technisch, kurz und prüfbar."
                    ),
                    options=deep_limits.get(
                        role,
                        {"num_ctx": 1536, "num_predict": 110, "temperature": 0.15},
                    ),
                    request_timeout=75.0,
                    retry_attempts=0,
                    keep_alive="15m",
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
