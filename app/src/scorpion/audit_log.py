from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|cookie|authorization)\s*[:=]\s*[^\s,;]+"
)


class AuditLog:
    """Local append-only metadata log. It intentionally excludes payload/body content."""

    def __init__(self, path: str | Path | None = None, *, max_bytes: int = 1_000_000):
        self.path = Path(path or (Path.home() / ".scorpion" / "audit.jsonl"))
        self.max_bytes = max(16_384, int(max_bytes))

    def _rotate_if_needed(self) -> None:
        try:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                rotated = self.path.with_suffix(self.path.suffix + ".1")
                if rotated.exists():
                    rotated.unlink()
                self.path.replace(rotated)
        except OSError:
            pass

    @staticmethod
    def _safe_text(value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        text = _SECRET_RE.sub(r"\1=[REDACTED]", text)
        return text[:160]

    def record(
        self,
        action_type: str,
        target: str | None,
        *,
        confirmation_required: bool,
        outcome: str,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": self._safe_text(action_type) or "unknown",
            "target": self._safe_text(target),
            "confirmation_required": bool(confirmation_required),
            "outcome": self._safe_text(outcome) or "unknown",
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
