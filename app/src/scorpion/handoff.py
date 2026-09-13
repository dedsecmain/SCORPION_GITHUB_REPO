from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class HandoffResult:
    prompt: str
    copied: bool
    opened: bool
    error: str | None = None


class ChatGPTHandoff:
    def __init__(
        self,
        *,
        history_limit: int = 8,
        clipboard_writer: Callable[[str], None] | None = None,
        browser_opener: Callable[[str], bool] | None = None,
    ):
        self.history_limit = max(0, int(history_limit))
        self.clipboard_writer = clipboard_writer or self._write_clipboard
        self.browser_opener = browser_opener or webbrowser.open

    @staticmethod
    def _write_clipboard(text: str) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        finally:
            root.destroy()

    def build_prompt(
        self,
        task: str,
        history: Iterable[dict[str, str]] = (),
        *,
        image_attached: bool = False,
    ) -> str:
        lines = [
            "SCORPION Mk II HANDOFF",
            "Du hilfst Scorpion, einem Windows-first persönlichen Assistenten. Antworte direkt auf die aktuelle Aufgabe.",
            "",
        ]
        recent = list(history)[-self.history_limit :] if self.history_limit else []
        if recent:
            lines.append("Letzter Gesprächskontext:")
            for item in recent:
                role = item.get("role", "user")
                content = item.get("content", "")
                if isinstance(content, str) and content.strip():
                    who = "Nutzer" if role == "user" else "Scorpion"
                    lines.append(f"{who}: {content.strip()}")
            lines.append("")

        lines.extend(["Aktuelle Aufgabe:", task.strip()])
        if image_attached:
            lines.extend(
                [
                    "",
                    "WICHTIG: Das zugehörige Bildschirm-/Kamerabild wurde nicht automatisch übertragen. Bitte das Bild manuell in ChatGPT anhängen, bevor diese Aufgabe beantwortet wird.",
                ]
            )
        return "\n".join(lines).strip()

    def copy_and_open(self, prompt: str) -> HandoffResult:
        copied = False
        opened = False
        errors: list[str] = []
        try:
            self.clipboard_writer(prompt)
            copied = True
        except Exception as exc:
            errors.append(f"Zwischenablage: {exc}")

        try:
            opened = bool(self.browser_opener("https://chatgpt.com/"))
            if not opened:
                errors.append("Browser konnte ChatGPT nicht öffnen.")
        except Exception as exc:
            errors.append(f"Browser: {exc}")

        return HandoffResult(
            prompt=prompt,
            copied=copied,
            opened=opened,
            error=" | ".join(errors) if errors else None,
        )
