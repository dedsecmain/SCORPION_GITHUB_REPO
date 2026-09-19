from scorpion import __version__
from scorpion.config import Settings


def test_mk47_version():
    assert __version__ == "47.0.0"


def test_default_natural_voice_is_high_german(monkeypatch):
    monkeypatch.delenv("SCORPION_NATURAL_VOICE", raising=False)
    settings = Settings.from_env()
    assert settings.natural_voice.startswith("de-DE-")
    assert "Swiss" not in settings.natural_voice



def test_mk50_defaults_wake_and_autostart_on(monkeypatch):
    monkeypatch.delenv("SCORPION_WAKE_LISTENER_ENABLED", raising=False)
    monkeypatch.delenv("SCORPION_AUTOSTART_ENABLED", raising=False)
    monkeypatch.delenv("SCORPION_BUILD_GESTURES_ENABLED", raising=False)
    settings = Settings.from_env()
    assert settings.wake_listener_enabled is True
    assert settings.autostart_enabled is True
    assert settings.build_gestures_enabled is True
