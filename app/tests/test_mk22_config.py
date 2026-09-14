from scorpion import __version__
from scorpion.config import Settings


def test_mk22_version():
    assert __version__ == "22.0.0"


def test_default_natural_voice_is_high_german(monkeypatch):
    monkeypatch.delenv("SCORPION_NATURAL_VOICE", raising=False)
    settings = Settings.from_env()
    assert settings.natural_voice.startswith("de-DE-")
    assert "Swiss" not in settings.natural_voice
