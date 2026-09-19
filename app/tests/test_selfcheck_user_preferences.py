from scorpion.selfcheck import run_selfcheck


def test_release_selfcheck_ignores_user_wake_and_autostart_preferences(monkeypatch):
    monkeypatch.setenv("SCORPION_WAKE_LISTENER_ENABLED", "false")
    monkeypatch.setenv("SCORPION_AUTOSTART_ENABLED", "false")

    assert run_selfcheck() == 0


def test_fresh_install_defaults_still_enable_wake_and_autostart(monkeypatch):
    from scorpion.config import Settings

    monkeypatch.delenv("SCORPION_WAKE_LISTENER_ENABLED", raising=False)
    monkeypatch.delenv("SCORPION_AUTOSTART_ENABLED", raising=False)

    settings = Settings.from_env()
    assert settings.wake_listener_enabled is True
    assert settings.autostart_enabled is True
