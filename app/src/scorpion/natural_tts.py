from __future__ import annotations

import asyncio
import ctypes
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Awaitable, Callable


Synthesizer = Callable[[str, Path, str, str, str, str], Awaitable[None]]
Player = Callable[[Path], None]


class NaturalVoiceService:
    """Natural Edge TTS with interruptible Windows playback."""

    def __init__(
        self,
        voice: str = "de-DE-KatjaNeural",
        *,
        rate: str = "-4%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        synthesizer: Synthesizer | None = None,
        player: Player | None = None,
        temp_dir: Path | str | None = None,
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self._synthesizer = synthesizer or self._edge_synthesize
        self._player = player or self._windows_mci_play
        self.temp_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
        self._stop_event = threading.Event()
        self._active_alias: str | None = None
        self._alias_lock = threading.Lock()

    @staticmethod
    def _speech_text(text: str) -> str:
        cleaned = re.sub(r"```.*?```", " Code-Block ausgelassen. ", text, flags=re.DOTALL)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"https?://\S+", " Link ", cleaned)
        cleaned = re.sub(r"[*_#>]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:6000]

    @staticmethod
    async def _edge_synthesize(
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
    ) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("edge-tts ist nicht installiert") from exc

        communicate = edge_tts.Communicate(
            text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(str(output_path))

    def _windows_mci_play(self, path: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("Neural-TTS-Wiedergabe ist für Windows ausgelegt.")

        winmm = ctypes.windll.winmm
        alias = f"scorpiontts_{uuid.uuid4().hex}"
        safe_path = str(path).replace('"', '""')

        def send(command: str, *, check: bool = True) -> None:
            code = int(winmm.mciSendStringW(command, None, 0, None))
            if code and check:
                buffer = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(code, buffer, len(buffer))
                raise RuntimeError(buffer.value or f"MCI Fehler {code}")

        try:
            send(f'open "{safe_path}" type mpegvideo alias {alias}')
            with self._alias_lock:
                self._active_alias = alias
            if self._stop_event.is_set():
                return
            send(f"play {alias} wait")
        finally:
            with self._alias_lock:
                if self._active_alias == alias:
                    self._active_alias = None
            try:
                send(f"close {alias}", check=False)
            except Exception:
                pass

    def stop(self) -> None:
        """Interrupt synthesis/playback without raising; idempotent."""
        self._stop_event.set()
        player_stop = getattr(self._player, "stop", None)
        if callable(player_stop):
            try:
                player_stop()
            except Exception:
                pass
        if os.name != "nt":
            return
        with self._alias_lock:
            alias = self._active_alias
        if not alias:
            return
        try:
            ctypes.windll.winmm.mciSendStringW(f"stop {alias}", None, 0, None)
        except Exception:
            pass

    def speak(self, text: str) -> bool:
        spoken = self._speech_text(text)
        if not spoken:
            return False

        self._stop_event.clear()
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        output = self.temp_dir / f"scorpion_voice_{uuid.uuid4().hex}.mp3"
        try:
            asyncio.run(
                self._synthesizer(
                    spoken,
                    output,
                    self.voice,
                    self.rate,
                    self.pitch,
                    self.volume,
                )
            )
            if self._stop_event.is_set():
                return False
            self._player(output)
            return not self._stop_event.is_set()
        except Exception:
            return False
        finally:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
