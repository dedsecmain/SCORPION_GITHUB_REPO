from scorpion.agent_team import LocalAgentTeam
from scorpion.model_router import ModelRoute


class FakeRouter:
    def __init__(self):
        self.routes = []
        self.results = []

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

    def respond(
        self,
        text,
        history=(),
        image_bytes=None,
        *,
        model=None,
        context=None,
        memory_context=None,
        think=None,
        options=None,
        request_timeout=None,
        retry_attempts=None,
    ):
        self.calls.append((text, model, think, options, request_timeout, retry_attempts))
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
    _prompt, _model, think, options, request_timeout, retry_attempts = ai.calls[0]
    assert think is False
    assert options["num_predict"] == 420
    assert request_timeout is None
    assert retry_attempts is None
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
    assert all(call[2] is False for call in ai.calls)
    assert all(call[4] == 85.0 for call in ai.calls)
    assert all(call[5] == 0 for call in ai.calls)
    assert [call[3]["num_predict"] for call in ai.calls] == [320, 240, 220]
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
