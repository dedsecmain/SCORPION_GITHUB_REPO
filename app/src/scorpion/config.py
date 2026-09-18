from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Mode(str, Enum):
    LOCAL = "LOCAL"
    HYBRID = "HYBRID"
    CLOUD = "CLOUD"

    @classmethod
    def from_value(cls, value: str | None) -> "Mode":
        normalized = (value or cls.LOCAL.value).strip().upper()
        try:
            return cls(normalized)
        except ValueError:
            return cls.LOCAL


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    transcription_model: str
    tts_model: str
    voice: str
    wake_word: str
    memory_path: Path
    mic_seconds: float
    wake_listener_seconds: float
    wake_listener_enabled: bool
    realtime_model: str
    mode: Mode = Mode.LOCAL
    local_model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    whisper_model: str = "base"
    natural_voice: str = "de-DE-KatjaNeural"
    natural_voice_rate: str = "-4%"
    natural_voice_pitch: str = "+0Hz"
    natural_voice_enabled: bool = True
    wake_wait_seconds: float = 20.0
    command_end_silence_ms: int = 800
    command_max_seconds: float = 30.0
    wake_whisper_model: str = "base"
    command_whisper_model: str = "auto"
    vad_aggressiveness: int = 2
    adaptive_path: Path = Path.home() / ".scorpion" / "adaptive.json"
    long_term_memory_path: Path = Path.home() / ".scorpion" / "long_term_memory.json"
    drive_sync_enabled: bool = False
    drive_folder: str = "ScorpionMemory"
    app_trust_path: Path = Path.home() / ".scorpion" / "app_trust.json"
    screen_context_enabled: bool = True
    screen_context_interval_ms: int = 1000
    github_repo: str = "dedsecmain/SCORPION_GITHUB_REPO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY") or None,
            model=os.getenv("SCORPION_MODEL", "gpt-5"),
            transcription_model=os.getenv("SCORPION_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
            tts_model=os.getenv("SCORPION_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("SCORPION_VOICE", "cedar"),
            wake_word=os.getenv("SCORPION_WAKE_WORD", "Scorpion"),
            memory_path=Path(os.getenv("SCORPION_MEMORY_PATH", str(Path.home() / ".scorpion" / "memory.json"))),
            mic_seconds=float(os.getenv("SCORPION_MIC_SECONDS", "6")),
            wake_listener_seconds=float(os.getenv("SCORPION_WAKE_LISTENER_SECONDS", "3")),
            wake_listener_enabled=_env_bool("SCORPION_WAKE_LISTENER_ENABLED", False),
            realtime_model=os.getenv("SCORPION_REALTIME_MODEL", "gpt-realtime-2"),
            mode=Mode.from_value(os.getenv("SCORPION_MODE")),
            local_model=os.getenv("SCORPION_LOCAL_MODEL", "").strip(),
            ollama_url=os.getenv("SCORPION_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            whisper_model=os.getenv("SCORPION_WHISPER_MODEL", "base"),
            natural_voice=os.getenv("SCORPION_NATURAL_VOICE", "de-DE-KatjaNeural"),
            natural_voice_rate=os.getenv("SCORPION_NATURAL_VOICE_RATE", "-4%"),
            natural_voice_pitch=os.getenv("SCORPION_NATURAL_VOICE_PITCH", "+0Hz"),
            natural_voice_enabled=_env_bool("SCORPION_NATURAL_VOICE_ENABLED", True),
            wake_wait_seconds=float(os.getenv("SCORPION_WAKE_WAIT_SECONDS", "20")),
            command_end_silence_ms=int(os.getenv("SCORPION_COMMAND_END_SILENCE_MS", "800")),
            command_max_seconds=float(os.getenv("SCORPION_COMMAND_MAX_SECONDS", "30")),
            wake_whisper_model=os.getenv("SCORPION_WAKE_WHISPER_MODEL", "base"),
            command_whisper_model=os.getenv("SCORPION_COMMAND_WHISPER_MODEL", "auto"),
            vad_aggressiveness=int(os.getenv("SCORPION_VAD_AGGRESSIVENESS", "2")),
            adaptive_path=Path(os.getenv("SCORPION_ADAPTIVE_PATH", str(Path.home() / ".scorpion" / "adaptive.json"))),
            long_term_memory_path=Path(
                os.getenv(
                    "SCORPION_LONG_TERM_MEMORY_PATH",
                    str(Path.home() / ".scorpion" / "long_term_memory.json"),
                )
            ),
            drive_sync_enabled=_env_bool("SCORPION_DRIVE_SYNC_ENABLED", False),
            drive_folder=os.getenv("SCORPION_DRIVE_FOLDER", "ScorpionMemory").strip() or "ScorpionMemory",
            app_trust_path=Path(
                os.getenv(
                    "SCORPION_APP_TRUST_PATH",
                    str(Path.home() / ".scorpion" / "app_trust.json"),
                )
            ),
            screen_context_enabled=_env_bool("SCORPION_SCREEN_CONTEXT_ENABLED", True),
            screen_context_interval_ms=max(
                100,
                int(os.getenv("SCORPION_SCREEN_CONTEXT_INTERVAL_MS", "1000")),
            ),
            github_repo=os.getenv("SCORPION_GITHUB_REPO", "dedsecmain/SCORPION_GITHUB_REPO").strip(),
        )
