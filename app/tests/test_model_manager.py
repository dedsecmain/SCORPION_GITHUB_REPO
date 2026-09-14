import pytest

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
