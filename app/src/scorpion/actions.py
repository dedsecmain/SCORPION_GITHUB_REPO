from __future__ import annotations

import os
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Literal

from .action_policy import ActionPolicy, ActionRisk
from .app_trust import AppTrustRegistry

Action = tuple[Literal["process", "url"], str]


WINDOWS_ACTIONS: dict[str, Action] = {
    "calculator": ("process", "calc.exe"),
    "notepad": ("process", "notepad.exe"),
    "explorer": ("process", "explorer.exe"),
    "browser": ("url", "https://www.google.com"),
}

WINDOW_APP_IDS: dict[str, str] = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "browser": "default-browser",
}

WINDOW_TARGETS: dict[str, tuple[str, ...]] = {
    "calculator": ("calculator", "rechner", "taschenrechner"),
    "notepad": ("notepad", "editor"),
    "explorer": ("file explorer", "explorer"),
    "browser": ("edge", "chrome", "firefox", "brave", "opera"),
}


@dataclass(frozen=True)
class ActionPreflight:
    allowed: bool
    requires_confirmation: bool
    risk: ActionRisk
    action: str
    target: str | None
    reason: str


def resolve_windows_action(target: str) -> Action | None:
    return WINDOWS_ACTIONS.get(target)


def resolve_window_target(target: str) -> tuple[str, ...] | None:
    return WINDOW_TARGETS.get(target)


def resolve_app_id(target: str) -> str | None:
    return WINDOW_APP_IDS.get(target)


def preflight_windows_action(
    action: str,
    target: str | None,
    *,
    trust_registry: AppTrustRegistry | None = None,
    policy: ActionPolicy | None = None,
) -> ActionPreflight:
    policy = policy or ActionPolicy()
    risk = policy.classify(action, target)
    requires_confirmation = policy.requires_confirmation(action, target)

    if target is None:
        return ActionPreflight(
            allowed=False,
            requires_confirmation=True,
            risk=risk,
            action=action,
            target=target,
            reason="Kein Ziel für die Aktion angegeben.",
        )

    app_id = resolve_app_id(target)
    if app_id is None:
        return ActionPreflight(
            allowed=False,
            requires_confirmation=True,
            risk=risk,
            action=action,
            target=target,
            reason="Diese Anwendung ist nicht in Scorpions lokaler App-Liste freigegeben.",
        )

    registry = trust_registry or AppTrustRegistry()
    if not registry.is_trusted(app_id):
        return ActionPreflight(
            allowed=False,
            requires_confirmation=True,
            risk=risk,
            action=action,
            target=target,
            reason=f"Erste Freigabe für {app_id} erforderlich.",
        )

    return ActionPreflight(
        allowed=True,
        requires_confirmation=requires_confirmation,
        risk=risk,
        action=action,
        target=target,
        reason=(
            "Aktion ist freigegeben."
            if not requires_confirmation
            else "Aktion benötigt vor der Ausführung eine konkrete Bestätigung."
        ),
    )


def execute_windows_action(
    target: str,
    *,
    trust_registry: AppTrustRegistry | None = None,
) -> tuple[bool, str]:
    action = resolve_windows_action(target)
    if action is None:
        return False, "Dieser lokale Befehl ist nicht freigegeben."

    preflight = preflight_windows_action(
        "open_app",
        target,
        trust_registry=trust_registry,
    )
    if not preflight.allowed:
        return False, preflight.reason
    if preflight.requires_confirmation:
        return False, preflight.reason

    if os.name != "nt":
        return False, "Lokale App-Befehle sind in dieser Version für Windows gedacht."

    kind, value = action
    try:
        if kind == "process":
            subprocess.Popen([value], shell=False)
        else:
            webbrowser.open(value)
        return True, f"{target} geöffnet."
    except OSError as exc:
        return False, f"Konnte {target} nicht öffnen: {exc}"


def focus_windows_target(
    target: str,
    *,
    trust_registry: AppTrustRegistry | None = None,
) -> tuple[bool, str]:
    keywords = resolve_window_target(target)
    if keywords is None:
        return False, "Dieses Fenster ist nicht freigegeben."

    preflight = preflight_windows_action(
        "focus_window",
        target,
        trust_registry=trust_registry,
    )
    if not preflight.allowed:
        return False, preflight.reason
    if preflight.requires_confirmation:
        return False, preflight.reason

    if os.name != "nt":
        return False, "Fenstersteuerung ist in Scorpion MK22 für Windows gedacht."

    try:
        import pygetwindow as gw
    except ImportError:
        return False, "Für Fenstersteuerung fehlt pygetwindow. Führe setup_scorpion.bat erneut aus."

    for window in gw.getAllWindows():
        title = (window.title or "").lower()
        if title and any(keyword in title for keyword in keywords):
            try:
                if window.isMinimized:
                    window.restore()
                window.activate()
                return True, f"{target} nach vorne geholt."
            except Exception as exc:
                return False, f"Konnte {target} nicht fokussieren: {exc}"
    return False, f"Kein offenes {target}-Fenster gefunden."
