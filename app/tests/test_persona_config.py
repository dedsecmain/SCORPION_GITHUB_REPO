from scorpion.config import Settings
from scorpion.persona import build_persona


def test_persona_has_identity_and_wake_name():
    prompt = build_persona()
    assert "Scorpion" in prompt
    assert "Windows" in prompt


def test_config_defaults_are_sane(monkeypatch):
    monkeypatch.delenv("SCORPION_MODEL", raising=False)
    settings = Settings.from_env()
    assert settings.model.startswith("gpt-")
    assert settings.wake_word.lower() == "scorpion"


def test_mk1_config_defaults(monkeypatch):
    monkeypatch.delenv("SCORPION_WAKE_LISTENER_SECONDS", raising=False)
    monkeypatch.delenv("SCORPION_WAKE_LISTENER_ENABLED", raising=False)
    monkeypatch.delenv("SCORPION_REALTIME_MODEL", raising=False)
    settings = Settings.from_env()
    assert 1.0 <= settings.wake_listener_seconds <= 8.0
    assert settings.wake_listener_enabled is False
    assert settings.realtime_model.startswith("gpt-realtime")


def test_natural_voice_defaults(monkeypatch):
    monkeypatch.delenv("SCORPION_NATURAL_VOICE", raising=False)
    monkeypatch.delenv("SCORPION_NATURAL_VOICE_RATE", raising=False)
    monkeypatch.delenv("SCORPION_NATURAL_VOICE_ENABLED", raising=False)
    settings = Settings.from_env()
    assert settings.natural_voice == "de-DE-KatjaNeural"
    assert settings.natural_voice_rate == "-4%"
    assert settings.natural_voice_enabled is True
