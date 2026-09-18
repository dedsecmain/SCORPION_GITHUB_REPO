import json

from scorpion.audit_log import AuditLog


def test_audit_log_records_only_safe_action_metadata(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record(
        "send_message",
        "notepad.exe",
        confirmation_required=True,
        outcome="denied",
    )
    line = path.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["action_type"] == "send_message"
    assert payload["target"] == "notepad.exe"
    assert payload["confirmation_required"] is True
    assert payload["outcome"] == "denied"
    assert set(payload) == {
        "timestamp",
        "action_type",
        "target",
        "confirmation_required",
        "outcome",
    }


def test_audit_log_sanitizes_secret_shaped_targets(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record(
        "change_setting",
        "password=hunter2 token=abc123",
        confirmation_required=True,
        outcome="blocked",
    )
    content = path.read_text(encoding="utf-8").lower()
    assert "hunter2" not in content
    assert "abc123" not in content
