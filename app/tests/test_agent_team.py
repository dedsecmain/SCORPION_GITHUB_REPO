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
    ):
        self.calls.append((text, model))
        if "Scorpion-coder" in text:
            return "CODER PLAN"
        if "Scorpion-tester" in text:
            assert "CODER PLAN" in text
            return "TEST REVIEW"
        assert "Scorpion-production-validator" in text
        assert "CODER PLAN" in text
        assert "TEST REVIEW" in text
        return "VALIDATED PLAN"


def test_local_agent_team_reuses_one_qwen_backend_sequentially():
    ai = FakeLocalAI()
    router = FakeRouter()
    team = LocalAgentTeam(ai, router)

    result = team.run("Verbessere den Build Mode")

    assert [stage.role for stage in result.stages] == [
        "coder",
        "tester",
        "production-validator",
    ]
    assert {stage.model for stage in result.stages} == {"qwen3.5:4b"}
    assert result.final_output == "VALIDATED PLAN"
    assert len(ai.calls) == 3
    assert all(model == "qwen3.5:4b" for _prompt, model in ai.calls)
    assert len(router.routes) == 1
    assert len(router.results) == 3
    assert all(success is True for _model, success, _latency in router.results)
