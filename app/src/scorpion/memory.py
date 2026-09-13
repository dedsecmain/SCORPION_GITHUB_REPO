from __future__ import annotations

import json
from pathlib import Path


class ConversationMemory:
    def __init__(self, path: str | Path, max_messages: int = 12):
        self.path = Path(path)
        self.max_messages = max_messages
        self._messages = self._load()

    def _load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        cleaned = []
        for item in data:
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
                cleaned.append({"role": item["role"], "content": item["content"]})
        return cleaned[-self.max_messages :]

    def append(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        self._messages.append({"role": role, "content": content})
        self._messages = self._messages[-self.max_messages :]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._messages, ensure_ascii=False, indent=2), encoding="utf-8")

    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages = []
        if self.path.exists():
            self.path.unlink()
