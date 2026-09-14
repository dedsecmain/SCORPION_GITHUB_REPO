from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .adaptive import AdaptiveStore
from .model_manager import ModelManager


class TaskKind(str, Enum):
    COMMAND = "command"
    CHAT = "chat"
    REASONING = "reasoning"
    VISION = "vision"
    CLOUD_CANDIDATE = "cloud_candidate"


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str | None = None
    requires_approval: bool = False
    reason: str = ""


class ModelRouter:
    def __init__(
        self,
        *,
        model_manager: ModelManager,
        hardware_profile,
        installed_models: set[str],
        adaptive_store: AdaptiveStore,
    ):
        self.model_manager = model_manager
        self.hardware_profile = hardware_profile
        self.installed_models = set(installed_models)
        self.adaptive_store = adaptive_store

    def _healthy(self, model: str) -> bool:
        item = (self.adaptive_store.get("model_metrics", {}) or {}).get(model, {})
        calls = int(item.get("calls", 0))
        failures = int(item.get("failures", 0))
        return not (calls >= 4 and failures / max(1, calls) >= 0.75)

    def _first_installed_healthy(self, candidates: tuple[str, ...]) -> str | None:
        for model in candidates:
            if model in self.installed_models and self._healthy(model):
                return model
        for model in candidates:
            if model in self.installed_models:
                return model
        return None

    def route(self, task: TaskKind, *, complexity: float = 0.5) -> ModelRoute:
        task = TaskKind(task)
        complexity = max(0.0, min(1.0, float(complexity)))

        if task is TaskKind.COMMAND:
            return ModelRoute("deterministic", reason="Deterministischer lokaler Befehl")
        if task is TaskKind.CLOUD_CANDIDATE:
            return ModelRoute("cloud", requires_approval=True, reason="Cloud-Nutzung braucht Freigabe")

        profile = getattr(self.hardware_profile, "capability", "low")
        if task is TaskKind.VISION:
            candidates = self.model_manager.role_candidates("vision", profile)
            model = self._first_installed_healthy(candidates)
            return ModelRoute("local", model=model, reason="Lokales Vision-Modell")

        if task is TaskKind.REASONING and complexity >= 0.75:
            candidates = self.model_manager.role_candidates("text", "performance")
        else:
            candidates = self.model_manager.role_candidates("text", "balanced")
        model = self._first_installed_healthy(candidates)
        return ModelRoute("local", model=model, reason="Adaptives lokales Text-Modell")

    def record_result(self, route: ModelRoute, *, latency_ms: float, success: bool) -> None:
        if route.provider != "local" or not route.model:
            return
        self.adaptive_store.record_model_performance(
            route.model,
            latency_ms=latency_ms,
            success=success,
        )
