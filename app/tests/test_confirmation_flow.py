from scorpion.action_policy import ActionRisk
from scorpion.actions import ActionPreflight, execute_preflighted_action
from scorpion.audit_log import AuditLog


def test_trusted_low_risk_action_runs_without_confirmation(tmp_path):
    calls = []
    confirms = []
    log = AuditLog(tmp_path / "audit.jsonl")
    preflight = ActionPreflight(True, False, ActionRisk.LOW, "open_app", "notepad", "ok")

    result = execute_preflighted_action(
        preflight,
        confirm=lambda pf: confirms.append(pf) or True,
        executor=lambda: calls.append("ran") or (True, "done"),
        audit_log=log,
    )

    assert result == (True, "done")
    assert calls == ["ran"]
    assert confirms == []


def test_mutating_action_never_executes_when_confirmation_is_denied(tmp_path):
    calls = []
    log = AuditLog(tmp_path / "audit.jsonl")
    preflight = ActionPreflight(True, True, ActionRisk.MUTATING, "change_setting", "notepad", "confirm")

    result = execute_preflighted_action(
        preflight,
        confirm=lambda _pf: False,
        executor=lambda: calls.append("ran") or (True, "done"),
        audit_log=log,
    )

    assert result[0] is False
    assert calls == []
    assert '"outcome": "denied"' in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_critical_action_requires_fresh_confirmation_each_time(tmp_path):
    confirmations = []
    executions = []
    preflight = ActionPreflight(True, True, ActionRisk.CRITICAL, "delete_file", "file.txt", "confirm")

    for _ in range(2):
        execute_preflighted_action(
            preflight,
            confirm=lambda _pf: confirmations.append("asked") or True,
            executor=lambda: executions.append("ran") or (True, "done"),
        )

    assert confirmations == ["asked", "asked"]
    assert executions == ["ran", "ran"]
