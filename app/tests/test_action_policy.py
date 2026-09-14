import pytest

from scorpion.action_policy import ActionPolicy, ActionRisk
from scorpion.actions import preflight_windows_action
from scorpion.app_trust import AppTrustRegistry


@pytest.mark.parametrize(
    "action",
    [
        "delete_file",
        "install_software",
        "uninstall_software",
        "send_message",
        "send_email",
        "post_content",
        "purchase",
        "change_security_settings",
        "run_elevated",
    ],
)
def test_critical_actions_always_require_confirmation(action):
    policy = ActionPolicy()
    assert policy.classify(action) is ActionRisk.CRITICAL
    assert policy.requires_confirmation(action) is True


@pytest.mark.parametrize("action", ["focus_window", "scroll", "navigate", "open_app", "read_state"])
def test_low_risk_actions_do_not_require_confirmation(action):
    policy = ActionPolicy()
    assert policy.classify(action) is ActionRisk.LOW
    assert policy.requires_confirmation(action) is False


@pytest.mark.parametrize("action", ["move_file", "rename_file", "change_setting", "edit_persistent_data"])
def test_mutating_actions_require_confirmation(action):
    policy = ActionPolicy()
    assert policy.classify(action) is ActionRisk.MUTATING
    assert policy.requires_confirmation(action) is True


def test_unknown_actions_fail_closed_as_critical():
    policy = ActionPolicy()
    assert policy.classify("do_something_new") is ActionRisk.CRITICAL
    assert policy.requires_confirmation("do_something_new") is True


def test_untrusted_app_is_blocked_until_explicitly_trusted(tmp_path):
    registry = AppTrustRegistry(tmp_path / "apps.json")
    result = preflight_windows_action(
        "open_app",
        "notepad",
        trust_registry=registry,
    )
    assert result.allowed is False
    assert result.requires_confirmation is True
    assert result.risk is ActionRisk.LOW

    registry.set_trust("notepad.exe", True)
    result = preflight_windows_action(
        "open_app",
        "notepad",
        trust_registry=registry,
    )
    assert result.allowed is True
    assert result.requires_confirmation is False
    assert result.risk is ActionRisk.LOW
