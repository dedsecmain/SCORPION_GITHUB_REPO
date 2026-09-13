from __future__ import annotations

import os
import subprocess
import webbrowser
from typing import Literal

Action = tuple[Literal["process", "url"], str]


WINDOWS_ACTIONS: dict[str, Action] = {
    "calculator": ("process", "calc.exe"),
    "notepad": ("process", "notepad.exe"),
    "explorer": ("process", "explorer.exe"),
    "browser": ("url", "https://www.google.com"),
}

WINDOW_TARGETS: dict[str, tuple[str, ...]] = {
    "calculator": ("calculator", "rechner", "taschenrechner"),
    "notepad": ("notepad", "editor"),
    "explorer": ("file explorer", "explorer"),
    "browser": ("edge", "chrome", "firefox", "brave", "opera"),
}


def resolve_windows_action(target: str) -> Action | None:
    return WINDOWS_ACTIONS.get(target)


def resolve_window_target(target: str) -> tuple[str, ...] | None:
    return WINDOW_TARGETS.get(target)


def execute_windows_action(target: str) -> tuple[bool, str]:
    action = resolve_windows_action(target)
    if action is None:
        return False, "Dieser lokale Befehl ist nicht freigegeben."
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


def focus_windows_target(target: str) -> tuple[bool, str]:
    keywords = resolve_window_target(target)
    if keywords is None:
        return False, "Dieses Fenster ist nicht freigegeben."
    if os.name != "nt":
        return False, "Fenstersteuerung ist in Mk I für Windows gedacht."

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
