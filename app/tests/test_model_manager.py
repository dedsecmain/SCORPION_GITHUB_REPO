import pytest

from scorpion.app import ScorpionController
from scorpion.model_manager import ModelManager, ModelRecommendation


def test_prefers_installed_quality_equivalent_model():
    manager = ModelManager()
    pick = manager.recommend(profile="balanced", installed_models={"qwen3:8b", "gemma3:4b"})
    assert pick.text_model == "qwen3:8b"
    assert pick.vision_model == "gemma3:4b"


def test_performance_prefers_larger_models_when_installed():
    manager = ModelManager()
    pick = manager.recommend(
        profile="performance",
        installed_models={"qwen3:14b", "gemma3:12b", "gemma3:4b"},
    )
    assert pick.text_model == "qwen3:14b"
    assert pick.vision_model == "gemma3:12b"


def test_vision_role_never_selects_text_only_models():
    manager = ModelManager()
    candidates = manager.role_candidates("vision", profile="performance")
    assert "gemma3:12b" in candidates
    assert "gemma3:4b" in candidates
    assert "qwen3:14b" not in candidates
    assert "qwen3:8b" not in candidates


def test_model_download_requires_confirmation():
    calls = []
    manager = ModelManager(runner=lambda args: calls.append(args) or 0)
    with pytest.raises(PermissionError):
        manager.pull("qwen3:8b", confirmed=False)
    assert calls == []
    manager.pull("qwen3:8b", confirmed=True)
    assert calls == [["ollama", "pull", "qwen3:8b"]]


def test_qwen35_4b_is_preferred_on_low_memory_when_installed():
    manager = ModelManager()
    pick = manager.recommend(
        profile="low",
        installed_models={"qwen3.5:4b", "gemma3:4b", "qwen3:8b"},
    )
    assert pick.text_model == "qwen3.5:4b"
    assert pick.vision_model == "gemma3:4b"


def test_qwen35_can_be_pulled_only_after_confirmation():
    calls = []
    manager = ModelManager(runner=lambda args: calls.append(args) or 0)
    manager.pull("qwen3.5:4b", confirmed=True)
    assert calls == [["ollama", "pull", "qwen3.5:4b"]]


def test_legacy_gemma_text_choice_migrates_to_qwen_when_available():
    class Adaptive:
        def __init__(self):
            self.data = {
                "text_model": "gemma3:4b",
                "vision_model": "gemma3:4b",
            }

        def get(self, key, default=None):
            return self.data.get(key, default)

        def set(self, key, value):
            self.data[key] = value

    class LocalAI:
        def available_models(self):
            return {"qwen3.5:4b", "gemma3:4b"}

    class Profiler:
        def profile(self):
            return "low"

    controller = ScorpionController.__new__(ScorpionController)
    controller.adaptive = Adaptive()
    controller.local_ai = LocalAI()
    controller.hardware_profiler = Profiler()
    controller.hardware_profile = None
    controller.model_manager = ModelManager()

    text_model, vision_model = controller._auto_select_models()

    assert text_model == "qwen3.5:4b"
    assert vision_model == "gemma3:4b"
    assert controller.adaptive.data["text_model"] == "qwen3.5:4b"
