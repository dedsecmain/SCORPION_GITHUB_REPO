from __future__ import annotations

import asyncio
import ctypes
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Awaitable, Callable


Synthesizer = Callable[[str, Path, str, str, str, str], Awaitable[None]]
Player = Callable[[Path], None]


class NaturalVoiceService:
    """Natural online TTS with no OpenAI dependency.

    Speech is synthesized with edge-tts (Microsoft's neural speech service).
    On Windows, MP3 playback uses the built-in MCI multimedia API so Scorpion
    does not need a separate media player or ffmpeg installation.
    """

    def __init__(
        self,
        voice: str = "de-CH-LeniNeural",
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

    @staticmethod
    def _speech_text(text: str) -> str:
        # Strip the markdown Scorpion often emits so the voice reads the answer,
        # not the formatting characters. Punctuation is kept because neural TTS
        # uses it for more human pauses and sentence melody.
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

    @staticmethod
    def _windows_mci_play(path: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("Neural-TTS-Wiedergabe ist in Mk II.1 auf Windows ausgelegt.")

        winmm = ctypes.windll.winmm
        alias = f"scorpiontts_{uuid.uuid4().hex}"
        safe_path = str(path).replace('"', '""')

        def send(command: str) -> None:
            code = int(winmm.mciSendStringW(command, None, 0, None))
            if code:
                buffer = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(code, buffer, len(buffer))
                raise RuntimeError(buffer.value or f"MCI Fehler {code}")

        try:
            send(f'open "{safe_path}" type mpegvideo alias {alias}')
            send(f"play {alias} wait")
        finally:
            # Closing an unopened alias can itself error, so ignore cleanup errors.
            try:
                winmm.mciSendStringW(f"close {alias}", None, 0, None)
            except Exception:
                pass

    def speak(self, text: str) -> bool:
        spoken = self._speech_text(text)
        if not spoken:
            return False

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
            self._player(output)
            return True
        except Exception:
            return False
        finally:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
