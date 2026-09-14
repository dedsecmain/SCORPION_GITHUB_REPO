from __future__ import annotations

import json
import os
from pathlib import Path


def normalize_app_id(app_id: str) -> str:
    """Return a stable lowercase application identity, never a window title."""
    value = str(app_id).strip().replace("\\", "/")
    value = value.rsplit("/", 1)[-1].strip().lower()
    if not value:
        raise ValueError("app_id must not be empty")
    return value


class AppTrustRegistry:
    """Local, atomic registry for explicit per-application trust decisions."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(
            path
            or os.getenv(
                "SCORPION_APP_TRUST_PATH",
                str(Path.home() / ".scorpion" / "app_trust.json"),
            )
        )
        self._trust: dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        raw_apps = payload.get("apps", payload)
        if not isinstance(raw_apps, dict):
            return
        for app_id, trusted in raw_apps.items():
            if not isinstance(trusted, bool):
                continue
            try:
                normalized = normalize_app_id(app_id)
            except ValueError:
                continue
            self._trust[normalized] = trusted

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        payload = {"apps": dict(sorted(self._trust.items()))}
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def is_trusted(self, app_id: str) -> bool:
        return self._trust.get(normalize_app_id(app_id), False)

    def set_trust(self, app_id: str, trusted: bool) -> None:
        self._trust[normalize_app_id(app_id)] = bool(trusted)
        self._persist()
