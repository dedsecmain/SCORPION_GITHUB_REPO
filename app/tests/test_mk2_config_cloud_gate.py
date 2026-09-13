from dataclasses import replace

import pytest

from scorpion.cloud_gate import CloudApprovalError, CloudGate
from scorpion.config import Mode, Settings


def test_mk2_defaults_to_local_without_api_key(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "SCORPION_MODE",
        "SCORPION_LOCAL_MODEL",
        "SCORPION_OLLAMA_URL",
        "SCORPION_WHISPER_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.api_key is None
    assert settings.mode is Mode.LOCAL
    assert settings.local_model == ""
    assert settings.ollama_url == "http://127.0.0.1:11434"
    assert settings.whisper_model == "base"


def test_mode_parser_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("SCORPION_MODE", "hybrid")
    assert Settings.from_env().mode is Mode.HYBRID


def test_cloud_gate_issues_one_use_token_only_after_approval():
    reasons = []
    gate = CloudGate(lambda reason: reasons.append(reason) or True)

    token = gate.request_approval("Analyse mit OpenAI")

    assert token is not None
    assert reasons == ["Analyse mit OpenAI"]
    gate.consume(token)
    with pytest.raises(CloudApprovalError):
        gate.consume(token)


def test_cloud_gate_denial_returns_no_token():
    gate = CloudGate(lambda _reason: False)
    assert gate.request_approval("Cloud") is None


def test_cloud_gate_rejects_foreign_token():
    first = CloudGate(lambda _reason: True)
    second = CloudGate(lambda _reason: True)
    token = first.request_approval("Cloud")
    assert token is not None
    with pytest.raises(CloudApprovalError):
        second.consume(token)
