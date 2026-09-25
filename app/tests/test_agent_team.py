from scorpion.agent_team import LocalAgentTeam
from scorpion.model_router import ModelRoute


class FakeRouter:
    def __init__(self):
        self.routes = []
        self.results = []
        self.installed_models = {"qwen3.5:4b", "gemma3:4b"}

    def route(self, task, *, complexity=0.5, priority="balanced"):
        self.routes.append((task, complexity, priority))
        return ModelRoute(
            provider="local",
            model="qwen3.5:4b",
            requires_approval=False,
            reason="test",
        )

    def record_result(self, route, *, latency_ms, success):
        self.results.append((route.model, success, latency_ms))


class FakeLocalAI:
    def __init__(self):
        self.calls = []

    def respond_agent(
        self,
        text,
        *,
        model=None,
        system_prompt=None,
        options=None,
        request_timeout=None,
        retry_attempts=None,
        keep_alive=None,
    ):
        self.calls.append(
            (text, model, system_prompt, options, request_timeout, retry_attempts, keep_alive)
        )
        if "schnelles lokales Entwicklungs-Team" in text:
            return "FAST VALIDATED PLAN"
        if "Scorpion-coder" in text:
            return "CODER PLAN"
        if "Scorpion-tester" in text:
            assert "CODER PLAN" in text
            return "TEST REVIEW"
        assert "Scorpion-production-validator" in text
        assert "CODER PLAN" in text
        assert "TEST REVIEW" in text
        return "VALIDATED PLAN"


def test_local_agent_team_fast_mode_uses_one_qwen_call():
    ai = FakeLocalAI()
    router = FakeRouter()
    team = LocalAgentTeam(ai, router)

    result = team.run("Verbessere den Build Mode")

    assert [stage.role for stage in result.stages] == ["fast-team"]
    assert result.stages[0].model == "qwen3.5:4b"
    assert len(ai.calls) == 1
    _prompt, model, system_prompt, options, request_timeout, retry_attempts, keep_alive = ai.calls[0]
    assert model == "qwen3.5:4b"
    assert "Fast-Team" in system_prompt
    assert options["num_ctx"] == 1536
    assert options["num_predict"] == 180
    assert request_timeout == 75.0
    assert retry_attempts == 0
    assert keep_alive == "15m"
    assert len(router.routes) == 1
    assert len(router.results) == 1
    assert router.results[0][1] is True


def test_local_agent_team_deep_mode_keeps_three_specialists():
    ai = FakeLocalAI()
    router = FakeRouter()
    team = LocalAgentTeam(ai, router)

    result = team.run("Verbessere den Build Mode", deep=True)

    assert [stage.role for stage in result.stages] == [
        "coder",
        "tester",
        "production-validator",
    ]
    assert {stage.model for stage in result.stages} == {"qwen3.5:4b"}
    assert result.final_output == "VALIDATED PLAN"
    assert len(ai.calls) == 3
    assert all(call[1] == "qwen3.5:4b" for call in ai.calls)
    assert all(call[4] == 75.0 for call in ai.calls)
    assert all(call[5] == 0 for call in ai.calls)
    assert all(call[6] == "15m" for call in ai.calls)
    assert [call[3]["num_predict"] for call in ai.calls] == [140, 110, 90]
    assert len(router.routes) == 1
    assert len(router.results) == 3


def test_local_agent_team_reports_progress_for_each_stage():
    ai = FakeLocalAI()
    router = FakeRouter()
    progress = []
    team = LocalAgentTeam(
        ai,
        router,
        progress_callback=lambda role, state, model: progress.append((role, state, model)),
    )

    team.run("Verbessere die Wakeword-Erkennung")

    assert progress == [
        ("fast-team", "start", "qwen3.5:4b"),
        ("fast-team", "done", "qwen3.5:4b"),
    ]


def test_ruflo_agent_path_prefers_qwen_even_if_router_would_choose_gemma():
    ai = FakeLocalAI()
    router = FakeRouter()

    def gemma_route(*_args, **_kwargs):
        return ModelRoute(
            provider="local",
            model="gemma3:4b",
            requires_approval=False,
            reason="historical fallback",
        )

    router.route = gemma_route
    team = LocalAgentTeam(ai, router)

    result = team.run("Verbessere die Wakeword-Erkennung")

    assert result.stages[0].model == "qwen3.5:4b"
    assert ai.calls[0][1] == "qwen3.5:4b"
