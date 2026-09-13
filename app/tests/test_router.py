from scorpion.local_ai import LocalModelMissingError, OllamaOfflineError
from scorpion.router import AssistantRouter, RouteStatus


class FakeLocalAI:
    def __init__(self, result="local answer", error=None):
        self.result = result
        self.error = error
        self.calls = []

    def respond(self, text, history=(), image_bytes=None):
        self.calls.append((text, list(history), image_bytes))
        if self.error:
            raise self.error
        return self.result


def test_router_returns_local_answer_without_cloud_dependency():
    local = FakeLocalAI()
    router = AssistantRouter(local)

    result = router.handle_local("hi", history=[{"role": "user", "content": "before"}])

    assert result.status is RouteStatus.ANSWER
    assert result.text == "local answer"
    assert local.calls[0][0] == "hi"


def test_router_offline_returns_escalation_choices():
    local = FakeLocalAI(error=OllamaOfflineError("offline"))
    router = AssistantRouter(local)

    result = router.handle_local("hi")

    assert result.status is RouteStatus.ESCALATION_REQUIRED
    assert "ChatGPT" in result.text
    assert "OpenAI" in result.text
    assert "lokal" in result.text.lower()


def test_router_model_missing_mentions_pull_command():
    local = FakeLocalAI(error=LocalModelMissingError("ollama pull gemma3:4b"))
    router = AssistantRouter(local)

    result = router.handle_local("hi")

    assert result.status is RouteStatus.ESCALATION_REQUIRED
    assert "ollama pull gemma3:4b" in result.text


def test_router_marks_image_for_manual_chatgpt_attachment_when_local_fails():
    local = FakeLocalAI(error=OllamaOfflineError("offline"))
    result = AssistantRouter(local).handle_local("look", image_bytes=b"jpeg")
    assert result.image_requires_manual_attachment is True


class ModelAwareFakeLocalAI:
    def __init__(self):
        self.calls = []

    def respond(self, text, history=(), image_bytes=None, *, model=None):
        self.calls.append((text, image_bytes, model))
        return "ok"


def test_router_passes_role_selected_model():
    local = ModelAwareFakeLocalAI()
    result = AssistantRouter(local).handle_local("hi", model="qwen3:8b")
    assert result.text == "ok"
    assert local.calls[-1][2] == "qwen3:8b"
