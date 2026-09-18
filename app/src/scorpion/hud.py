from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VoiceVisualState(str, Enum):
    STANDBY = "standby"
    ACKNOWLEDGED = "acknowledged"
    WAITING = "waiting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass(frozen=True)
class SystemPanelModel:
    voice_label: str = "STANDBY"
    countdown_visible: bool = False
    remaining: float | None = None
    core_state: VoiceVisualState = VoiceVisualState.STANDBY
    text_model: str = "AUTO"
    vision_model: str = "AUTO"
    hardware_label: str = "HARDWARE CHECKING"
    speech_label: str = "LOCAL SPEECH"
    ollama_label: str = "OLLAMA CHECKING"
    cloud_label: str = "OPENAI LOCKED 🔒"
    active_app_label: str = "NO ACTIVE APP"
    screen_context_label: str = "LOCAL CONTEXT OFF"
    mic_level: float = 0.0

    @classmethod
    def from_voice_state(cls, state, *, remaining: float | None = None, **kwargs):
        value = getattr(state, "value", state)
        value = str(value).upper()
        mapping = {
            "STANDBY": (VoiceVisualState.STANDBY, "STANDBY", False),
            "ACKNOWLEDGED": (VoiceVisualState.ACKNOWLEDGED, "ACKNOWLEDGED", False),
            "WAITING_COMMAND": (
                VoiceVisualState.WAITING,
                f"WAITING {max(0, int(round(remaining if remaining is not None else 20)))}s",
                True,
            ),
            "LISTENING": (VoiceVisualState.LISTENING, "LISTENING", False),
            "THINKING": (VoiceVisualState.THINKING, "THINKING", False),
            "SPEAKING": (VoiceVisualState.SPEAKING, "SPEAKING", False),
            "ERROR": (VoiceVisualState.ERROR, "ERROR", False),
        }
        core_state, label, visible = mapping.get(value, mapping["STANDBY"])
        return cls(
            voice_label=label,
            countdown_visible=visible,
            remaining=remaining,
            core_state=core_state,
            **kwargs,
        )


THEME = {
    "bg": "#090D12",
    "panel": "#111821",
    "panel_alt": "#151E29",
    "border": "#223142",
    "text": "#E8F2FF",
    "muted": "#8293A8",
    "cyan": "#34D6FF",
    "cyan_dim": "#123748",
    "orange": "#FF9F43",
    "danger": "#FF5F6D",
    "success": "#4ADE80",
}
