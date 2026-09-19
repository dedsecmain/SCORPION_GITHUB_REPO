from scorpion.selfcheck import run_selfcheck


def test_release_selfcheck_ignores_user_wake_and_autostart_preferences(monkeypatch):
    monkeypatch.setenv("SCORPION_WAKE_LISTENER_ENABLED", "false")
    monkeypatch.setenv("SCORPION_AUTOSTART_ENABLED", "false")

    assert run_selfcheck() == 0
