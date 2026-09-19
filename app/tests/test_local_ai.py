import base64

import pytest

from scorpion.local_ai import LocalModelMissingError, OllamaLocalAI, OllamaOfflineError


class FakeTransport:
    def __init__(self, tags=None, chat_response=None, fail=False):
        self.tags = tags if tags is not None else {"models": [{"name": "gemma3:4b"}]}
        self.chat_response = chat_response or {"message": {"content": "lokale antwort"}}
        self.fail = fail
        self.calls = []

    def __call__(self, method, url, payload=None, timeout=5.0):
        self.calls.append((method, url, payload, timeout))
        if self.fail:
            raise OSError("offline")
        if url.endswith("/api/tags"):
            return self.tags
        if url.endswith("/api/chat"):
            return self.chat_response
        raise AssertionError(url)


def test_status_ready_and_model_missing():
    ready = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=FakeTransport())
    assert ready.status().state == "ready"

    missing = OllamaLocalAI(
        "http://127.0.0.1:11434",
        "gemma3:4b",
        transport=FakeTransport(tags={"models": [{"name": "llama3.2:3b"}]}),
    )
    status = missing.status()
    assert status.state == "model_missing"
    assert "ollama pull gemma3:4b" in status.detail


def test_status_offline_is_human_readable():
    ai = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=FakeTransport(fail=True))
    status = ai.status()
    assert status.state == "offline"
    assert "Ollama" in status.detail


def test_respond_formats_text_history_and_bounds_it():
    transport = FakeTransport()
    ai = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=transport, history_limit=3)
    history = [{"role": "user", "content": f"m{i}"} for i in range(8)]

    answer = ai.respond("jetzt", history=history)

    assert answer == "lokale antwort"
    method, url, payload, _ = transport.calls[-1]
    assert method == "POST"
    assert url.endswith("/api/chat")
    assert payload["model"] == "gemma3:4b"
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "system"
    assert [m["content"] for m in payload["messages"][1:-1]] == ["m5", "m6", "m7"]
    assert payload["messages"][-1] == {"role": "user", "content": "jetzt"}


def test_respond_formats_image_as_ollama_base64():
    transport = FakeTransport()
    ai = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=transport)

    ai.respond("was siehst du", image_bytes=b"jpeg")

    payload = transport.calls[-1][2]
    user = payload["messages"][-1]
    assert user["images"] == [base64.b64encode(b"jpeg").decode("ascii")]


def test_respond_raises_specific_errors_before_chat_call():
    missing_transport = FakeTransport(tags={"models": []})
    missing = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=missing_transport)
    with pytest.raises(LocalModelMissingError):
        missing.respond("hi")
    assert not any(call[1].endswith("/api/chat") for call in missing_transport.calls)

    offline = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=FakeTransport(fail=True))
    with pytest.raises(OllamaOfflineError):
        offline.respond("hi")


def test_respond_can_use_explicit_role_model():
    transport = FakeTransport(tags={"models": [{"name": "qwen3:8b"}, {"name": "gemma3:12b"}]})
    ai = OllamaLocalAI("http://127.0.0.1:11434", "qwen3:8b", transport=transport)
    ai.respond("look", image_bytes=b"jpeg", model="gemma3:12b")
    payload = transport.calls[-1][2]
    assert payload["model"] == "gemma3:12b"



def test_system_prompt_uses_current_request_for_mk50_style():
    transport = FakeTransport()
    ai = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=transport)

    ai.respond("Ich habe starke Schmerzen und brauche Hilfe")

    payload = transport.calls[-1][2]
    system_prompt = payload["messages"][0]["content"]
    assert "Scorpion MK50" in system_prompt
    assert "Aktueller Reaktionsmodus: SERIOUS" in system_prompt
    assert "keine Witze" in system_prompt



def test_mk50_system_prompt_includes_relevant_memory_context():
    from scorpion.context_engine import analyze_context

    transport = FakeTransport()
    ai = OllamaLocalAI("http://127.0.0.1:11434", "gemma3:4b", transport=transport)
    context = analyze_context("Was ist beim Scorpion Update geplant?")
    ai.respond(
        "Was ist beim Scorpion Update geplant?",
        context=context,
        memory_context="MK50: Ollama Stabilität verbessern.",
    )
    payload = transport.calls[-1][2]
    system_prompt = payload["messages"][0]["content"]
    assert "Scorpion MK50" in system_prompt
    assert "Hochdeutsch" in system_prompt
    assert "MK50: Ollama Stabilität verbessern." in system_prompt



def test_ollama_transient_failure_recovers_without_cloud():
    class FlakyTransport:
        def __init__(self):
            self.calls = 0

        def __call__(self, method, url, payload=None, timeout=5.0):
            self.calls += 1
            if self.calls <= 2:
                raise OSError("temporary connection reset")
            if url.endswith("/api/tags"):
                return {"models": [{"name": "gemma3:4b"}]}
            return {"message": {"content": "wieder online"}}

    transport = FlakyTransport()
    ai = OllamaLocalAI(
        "http://127.0.0.1:11434",
        "gemma3:4b",
        transport=transport,
        retry_attempts=2,
        retry_delay=0,
    )
    assert ai.status().state == "ready"
    assert transport.calls == 3


def test_ollama_retry_is_bounded_and_reports_offline():
    class DeadTransport:
        def __init__(self):
            self.calls = 0

        def __call__(self, method, url, payload=None, timeout=5.0):
            self.calls += 1
            raise TimeoutError("dead")

    transport = DeadTransport()
    ai = OllamaLocalAI(
        "http://127.0.0.1:11434",
        "gemma3:4b",
        transport=transport,
        retry_attempts=2,
        retry_delay=0,
    )
    status = ai.status()
    assert status.state == "offline"
    assert transport.calls == 3
