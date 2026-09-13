from __future__ import annotations

import json
from pathlib import Path


ALLOWED_KEYS = {
    "accepted_wake_aliases",
    "wake_alias_success",
    "false_trigger_counts",
    "vad_aggressiveness",
    "mic_device",
    "wake_whisper_model",
    "command_whisper_model",
    "model_metrics",
    "text_model",
    "vision_model",
    "voice",
    "voice_rate",
    "voice_pitch",
    "ui",
}


def _ensure_json_safe(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("Adaptive settings dürfen keine Rohdaten-Bytes speichern.")
    try:
        json.dumps(value)
    except TypeError as exc:
        raise TypeError("Adaptive setting ist nicht JSON-kompatibel.") from exc


class AdaptiveStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._data = self._load()
        self._alias_sessions: dict[str, set[str]] = {}

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "accepted_wake_aliases": [],
                "wake_alias_success": {},
                "false_trigger_counts": {},
                "model_metrics": {},
            }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        if key not in ALLOWED_KEYS:
            raise KeyError(f"Adaptive key nicht erlaubt: {key}")
        _ensure_json_safe(value)
        self._data[key] = value
        self._save()

    def observe_wake_alias(self, alias: str, *, session_id: str, successful: bool) -> None:
        normalized = alias.strip().casefold()
        if not normalized:
            return
        sessions = self._alias_sessions.setdefault(normalized, set())
        if successful:
            sessions.add(str(session_id))
        counts = dict(self._data.get("wake_alias_success", {}))
        counts[normalized] = max(int(counts.get(normalized, 0)), len(sessions))
        self._data["wake_alias_success"] = counts
        self._save()

    def alias_ready(self, alias: str) -> bool:
        normalized = alias.strip().casefold()
        return int(self._data.get("wake_alias_success", {}).get(normalized, 0)) >= 3

    def activate_alias(self, alias: str, *, confirmed: bool) -> bool:
        normalized = alias.strip().casefold()
        if not confirmed or not self.alias_ready(normalized):
            return False
        aliases = list(self._data.get("accepted_wake_aliases", []))
        if normalized not in aliases:
            aliases.append(normalized)
            self._data["accepted_wake_aliases"] = aliases
            self._save()
        return True

    def record_model_metric(self, model: str, *, latency_s: float | None = None, success: bool = True) -> None:
        metrics = dict(self._data.get("model_metrics", {}))
        item = dict(metrics.get(model, {"runs": 0, "failures": 0, "latency_total": 0.0}))
        item["runs"] = int(item.get("runs", 0)) + 1
        if not success:
            item["failures"] = int(item.get("failures", 0)) + 1
        if latency_s is not None:
            item["latency_total"] = float(item.get("latency_total", 0.0)) + max(0.0, float(latency_s))
        metrics[model] = item
        self._data["model_metrics"] = metrics
        self._save()
