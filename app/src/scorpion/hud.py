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
    intelligence_label: str = "GENERAL · AUTO"
    improvement_label: str = "IDEAS 0"
    autonomy_label: str = "LOCAL-FIRST"
    proactive_label: str = "NO SUGGESTION"
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
    "bg": "#030304",
    "panel": "#0A0A0D",
    "panel_alt": "#101014",
    "rail": "#070709",
    "border": "#5E0B12",
    "border_hot": "#B5121B",
    "text": "#FFF2F2",
    "muted": "#B5797F",
    # Legacy key names are kept so existing widgets inherit the red redesign
    # without breaking functionality.
    "cyan": "#FF1F2D",
    "cyan_dim": "#3A090E",
    "orange": "#FF6B2D",
    "danger": "#FF0A1A",
    "success": "#FF3B47",
    "glow": "#FF3542",
    "accent": "#FF101F",
    "accent_bright": "#FF5A63",
    "input": "#08080A",
    "scanline": "#2A070B",
    "core_fill": "#23070B",
}


RED_HOLO_STATE_PALETTE = {
    VoiceVisualState.STANDBY: ("#6B0D15", "#190609", "#FF1F2D"),
    VoiceVisualState.ACKNOWLEDGED: ("#FF3542", "#24070B", "#FF5963"),
    VoiceVisualState.WAITING: ("#FF1F2D", "#25070B", "#FF3542"),
    VoiceVisualState.LISTENING: ("#FF2B38", "#2E080D", "#FF4B56"),
    VoiceVisualState.THINKING: ("#FF6B2D", "#32150A", "#FF7D3F"),
    VoiceVisualState.SPEAKING: ("#FF3542", "#2D080D", "#FF5963"),
    VoiceVisualState.ERROR: ("#FF0015", "#350006", "#FF0015"),
}
