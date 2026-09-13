from __future__ import annotations

import math
import struct


class VADUnavailableError(RuntimeError):
    pass


class VADSegmenter:
    VALID_FRAME_MS = {10, 20, 30}
    VALID_SAMPLE_RATES = {8000, 16000, 32000, 48000}

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        aggressiveness: int = 2,
        *,
        vad_engine=None,
    ):
        self.sample_rate = int(sample_rate)
        self.frame_ms = int(frame_ms)
        if self.sample_rate not in self.VALID_SAMPLE_RATES:
            raise ValueError("unsupported sample_rate for VAD")
        if self.frame_ms not in self.VALID_FRAME_MS:
            raise ValueError("frame_ms must be 10, 20, or 30")
        if not 0 <= int(aggressiveness) <= 3:
            raise ValueError("aggressiveness must be 0..3")
        self.aggressiveness = int(aggressiveness)
        self._vad = vad_engine or self._create_default_vad()
        self.frame_samples = self.sample_rate * self.frame_ms // 1000
        self.frame_bytes = self.frame_samples * 2

    def _create_default_vad(self):
        try:
            import webrtcvad
        except ImportError as exc:
            raise VADUnavailableError(
                "webrtcvad fehlt. Führe setup_scorpion.bat erneut aus."
            ) from exc
        return webrtcvad.Vad(self.aggressiveness)

    def is_speech(self, pcm_frame: bytes) -> bool:
        if len(pcm_frame) != self.frame_bytes:
            raise ValueError(
                f"frame must be exactly {self.frame_bytes} bytes for "
                f"{self.frame_ms}ms at {self.sample_rate}Hz"
            )
        return bool(self._vad.is_speech(pcm_frame, self.sample_rate))

    @staticmethod
    def rms_level(pcm_frame: bytes) -> float:
        if len(pcm_frame) % 2:
            raise ValueError("16-bit PCM frame must have an even byte length")
        if not pcm_frame:
            return 0.0
        count = len(pcm_frame) // 2
        samples = struct.unpack(f"<{count}h", pcm_frame)
        mean_square = sum(sample * sample for sample in samples) / count
        return min(1.0, math.sqrt(mean_square) / 32768.0)
