from pathlib import Path

from scorpion.config import Mode, Settings


def test_mk3_defaults_are_local_and_twenty_seconds(monkeypatch):
    for name in (
        "SCORPION_MODE",
        "SCORPION_LOCAL_MODEL",
        "SCORPION_WAKE_WAIT_SECONDS",
        "SCORPION_COMMAND_WHISPER_MODEL",
        "SCORPION_WAKE_WHISPER_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.mode is Mode.LOCAL
    assert settings.local_model == ""
    assert settings.wake_wait_seconds == 20.0
    assert settings.command_whisper_model == "auto"
    assert settings.wake_whisper_model == "base"


def test_setup_installs_mk3_dependencies():
    text = Path("requirements.txt").read_text(encoding="utf-8").lower()
    assert "webrtcvad" in text
    assert "psutil" in text
    assert "cryptography" in text


def test_update_channel_is_disabled_when_repo_missing(monkeypatch):
    monkeypatch.delenv("SCORPION_GITHUB_REPO", raising=False)
    assert Settings.from_env().github_repo == ""
