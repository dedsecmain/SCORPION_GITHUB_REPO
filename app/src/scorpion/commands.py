from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandKind(str, Enum):
    CHAT = "chat"
    OPEN_APP = "open_app"
    FOCUS_APP = "focus_app"
    CAMERA = "camera"
    SCREEN = "screen"
    BUILD_MODE = "build_mode"


@dataclass(frozen=True)
class ParsedCommand:
    kind: CommandKind
    target: str | None = None


_APP_TERMS = {
    "calculator": ("rechner", "taschenrechner", "calculator"),
    "browser": ("browser", "internet", "edge", "chrome", "firefox", "brave"),
    "notepad": ("editor", "notepad", "texteditor"),
    "explorer": ("explorer", "dateien", "ordner"),
}


def _target_from_text(text: str) -> str | None:
    for target, terms in _APP_TERMS.items():
        if any(term in text for term in terms):
            return target
    return None


def parse_command(text: str) -> ParsedCommand:
    t = " ".join(text.lower().strip().split())

    build_terms = ("build mode", "build-mode", "buildmodus", "bau modus", "baumodus")
    if any(term in t for term in build_terms):
        return ParsedCommand(CommandKind.BUILD_MODE, "build_mode")

    screen_terms = ("bildschirm", "screen", "desktop", "monitor")
    screen_verbs = ("was ist", "was siehst", "zeig", "analys", "schau", "sieh")
    if any(term in t for term in screen_terms) and any(v in t for v in screen_verbs):
        return ParsedCommand(CommandKind.SCREEN, "screen")

    camera_terms = ("kamera", "camera", "webcam")
    if any(term in t for term in camera_terms) and any(v in t for v in ("öffne", "zeig", "starte", "mach", "sieh", "schau")):
        return ParsedCommand(CommandKind.CAMERA, "camera")

    focus_verbs = ("wechsel zu", "wechsel zum", "fokussiere", "focus", "geh zu", "bring nach vorne")
    if any(v in t for v in focus_verbs):
        target = _target_from_text(t)
        if target:
            return ParsedCommand(CommandKind.FOCUS_APP, target)

    open_verbs = ("öffne", "aufmachen", "mach", "starte", "launch")
    if any(v in t for v in open_verbs):
        target = _target_from_text(t)
        if target:
            return ParsedCommand(CommandKind.OPEN_APP, target)

    return ParsedCommand(CommandKind.CHAT)
