from __future__ import annotations

import subprocess
from dataclasses import dataclass


MODEL_CATALOG = {
    "gemma3:4b": {"tier": "low", "vision": True},
    "qwen3:8b": {"tier": "balanced", "vision": False},
    "gemma3:12b": {"tier": "performance", "vision": True},
    "qwen3:14b": {"tier": "performance", "vision": False},
}


@dataclass(frozen=True)
class ModelRecommendation:
    text_model: str
    vision_model: str
    reason: str


class ModelManager:
    def __init__(self, *, runner=None):
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(args):
        return subprocess.run(args, check=False).returncode

    def role_candidates(self, role: str, profile) -> tuple[str, ...]:
        capability = profile if isinstance(profile, str) else getattr(profile, "capability", "low")
        normalized_role = str(role).strip().lower()

        if normalized_role == "text":
            if capability == "performance":
                candidates = ("qwen3:14b", "qwen3:8b", "gemma3:4b")
            elif capability == "balanced":
                candidates = ("qwen3:8b", "gemma3:4b")
            else:
                candidates = ("gemma3:4b", "qwen3:8b")
            return candidates

        if normalized_role == "vision":
            if capability == "performance":
                candidates = ("gemma3:12b", "gemma3:4b")
            elif capability == "balanced":
                candidates = ("gemma3:4b", "gemma3:12b")
            else:
                candidates = ("gemma3:4b",)
            return tuple(model for model in candidates if MODEL_CATALOG.get(model, {}).get("vision") is True)

        raise ValueError(f"Unbekannte Modellrolle: {role}")

    @staticmethod
    def _choose(candidates: tuple[str, ...], installed: set[str]) -> str:
        for model in candidates:
            if model in installed:
                return model
        if not candidates:
            raise RuntimeError("Für diese Modellrolle sind keine Kandidaten definiert.")
        return candidates[0]

    def recommend(self, profile, installed_models: set[str] | None = None) -> ModelRecommendation:
        capability = profile if isinstance(profile, str) else getattr(profile, "capability", "low")
        installed = set(installed_models or ())
        text_candidates = self.role_candidates("text", capability)
        vision_candidates = self.role_candidates("vision", capability)
        text = self._choose(text_candidates, installed)
        vision = self._choose(vision_candidates, installed)
        return ModelRecommendation(text, vision, f"Hardware-Profil: {capability}")

    def pull(self, model: str, *, confirmed: bool) -> int:
        if not confirmed:
            raise PermissionError("Modelldownload benötigt ausdrückliche Bestätigung.")
        if model not in MODEL_CATALOG:
            raise ValueError("Unbekanntes Modell.")
        return int(self._runner(["ollama", "pull", model]))
