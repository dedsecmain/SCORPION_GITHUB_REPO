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

    def record_model_performance(self, model: str, *, latency_ms: float, success: bool) -> None:
        metrics = dict(self._data.get("model_metrics", {}))
        item = dict(metrics.get(model, {}))
        calls = int(item.get("calls", 0)) + 1
        successes = int(item.get("successes", 0)) + (1 if success else 0)
        failures = int(item.get("failures", 0)) + (0 if success else 1)
        latency = max(0.0, float(latency_ms))
        previous = float(item.get("ema_latency_ms", latency))
        ema = latency if calls == 1 else (0.3 * latency + 0.7 * previous)
        metrics[model] = {
            "calls": calls,
            "successes": successes,
            "failures": failures,
            "ema_latency_ms": round(ema, 3),
        }
        self._data["model_metrics"] = metrics
        self._save()

    def record_model_metric(self, model: str, *, latency_s: float | None = None, success: bool = True) -> None:
        self.record_model_performance(
            model,
            latency_ms=max(0.0, float(latency_s or 0.0)) * 1000.0,
            success=success,
        )
