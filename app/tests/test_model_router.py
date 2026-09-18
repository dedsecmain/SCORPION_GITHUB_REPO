from scorpion.adaptive import AdaptiveStore
from scorpion.hardware import HardwareProfile
from scorpion.model_manager import ModelManager
from scorpion.model_router import ModelRouter, TaskKind


def performance_profile():
    return HardwareProfile(
        capability="performance",
        total_ram_gb=64,
        available_ram_gb=40,
        vram_gb=16,
        cpu_logical=24,
        cpu_physical=12,
        gpu_name="Test GPU",
    )


def make_router(tmp_path):
    return ModelRouter(
        model_manager=ModelManager(),
        hardware_profile=performance_profile(),
        installed_models={"gemma3:4b", "gemma3:12b", "qwen3:8b", "qwen3:14b"},
        adaptive_store=AdaptiveStore(tmp_path / "adaptive.json"),
    )


def test_simple_command_uses_deterministic_local_path(tmp_path):
    router = make_router(tmp_path)
    route = router.route(TaskKind.COMMAND)
    assert route.provider == "deterministic"
    assert route.model is None
    assert route.requires_approval is False


def test_cloud_candidate_never_bypasses_approval(tmp_path):
    router = make_router(tmp_path)
    route = router.route(TaskKind.CLOUD_CANDIDATE, complexity=1.0)
    assert route.provider == "cloud"
    assert route.requires_approval is True


def test_vision_uses_installed_vision_role(tmp_path):
    router = make_router(tmp_path)
    route = router.route(TaskKind.VISION)
    assert route.provider == "local"
    assert route.model == "gemma3:12b"
    assert route.requires_approval is False


def test_high_complexity_text_prefers_stronger_installed_model(tmp_path):
    router = make_router(tmp_path)
    route = router.route(TaskKind.REASONING, complexity=0.9)
    assert route.provider == "local"
    assert route.model == "qwen3:14b"


def test_normal_chat_avoids_heaviest_model_when_balanced_option_exists(tmp_path):
    router = make_router(tmp_path)
    route = router.route(TaskKind.CHAT, complexity=0.2)
    assert route.model == "qwen3:8b"


def test_repeated_failures_demote_a_model_without_storing_content(tmp_path):
    router = make_router(tmp_path)
    strong = router.route(TaskKind.REASONING, complexity=0.95)
    assert strong.model == "qwen3:14b"

    for _ in range(4):
        router.record_result(strong, latency_ms=5000, success=False)

    fallback = router.route(TaskKind.REASONING, complexity=0.95)
    assert fallback.model == "qwen3:8b"
    metrics = router.adaptive_store.get("model_metrics")
    assert set(metrics["qwen3:14b"]) == {
        "calls",
        "successes",
        "failures",
        "ema_latency_ms",
    }
