from __future__ import annotations

from enum import Enum


class ActionRisk(str, Enum):
    LOW = "low"
    MUTATING = "mutating"
    CRITICAL = "critical"


class ActionPolicy:
    ALIASES = {
        "show_status": "read_state",
        "check_status": "read_state",
        "inspect_screen": "read_state",
        "show_screen": "read_state",
        "list_files": "read_state",
        "read_file": "read_state",
        "check_updates": "read_state",
    }
    LOW_RISK = {
        "focus_window",
        "scroll",
        "navigate",
        "open_app",
        "read_state",
    }
    MUTATING = {
        "move_file",
        "rename_file",
        "change_setting",
        "edit_persistent_data",
    }
    CRITICAL = {
        "delete_file",
        "install_software",
        "uninstall_software",
        "send_message",
        "send_email",
        "post_content",
        "purchase",
        "change_security_settings",
        "run_elevated",
    }

    def classify(self, action: str, target: str | None = None) -> ActionRisk:
        _ = target
        normalized = str(action).strip().lower()
        normalized = self.ALIASES.get(normalized, normalized)
        if normalized in self.LOW_RISK:
            return ActionRisk.LOW
        if normalized in self.MUTATING:
            return ActionRisk.MUTATING
        if normalized in self.CRITICAL:
            return ActionRisk.CRITICAL
        return ActionRisk.CRITICAL

    def requires_confirmation(self, action: str, target: str | None = None) -> bool:
        return self.classify(action, target) is not ActionRisk.LOW
