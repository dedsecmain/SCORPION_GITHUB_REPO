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

    def recommend(self, profile, installed_models: set[str] | None = None) -> ModelRecommendation:
        capability = profile if isinstance(profile, str) else getattr(profile, "capability", "low")
        installed = set(installed_models or ())
        if capability == "performance":
            text_candidates = ["qwen3:14b", "qwen3:8b", "gemma3:4b"]
            vision_candidates = ["gemma3:12b", "gemma3:4b"]
        elif capability == "balanced":
            text_candidates = ["qwen3:8b", "gemma3:4b"]
            vision_candidates = ["gemma3:4b", "gemma3:12b"]
        else:
            text_candidates = ["gemma3:4b", "qwen3:8b"]
            vision_candidates = ["gemma3:4b"]

        def choose(candidates):
            for model in candidates:
                if model in installed:
                    return model
            return candidates[0]

        text = choose(text_candidates)
        vision = choose(vision_candidates)
        return ModelRecommendation(text, vision, f"Hardware-Profil: {capability}")

    def pull(self, model: str, *, confirmed: bool) -> int:
        if not confirmed:
            raise PermissionError("Modelldownload benötigt ausdrückliche Bestätigung.")
        if model not in MODEL_CATALOG:
            raise ValueError("Unbekanntes Modell.")
        return int(self._runner(["ollama", "pull", model]))
