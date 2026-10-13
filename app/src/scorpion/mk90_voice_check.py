"""MK90 local Voice Core decoder smoke test.

Runs without microphone permission, model downloads, cloud requests or Whisper
inference. Exercises the exact faster-whisper/PyAV audio decode path used in
local transcription with a generated temporary WAV sample.
"""
from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path


def check_local_decoder() -> tuple[bool, str]:
    try:
        import av
        from faster_whisper.audio import decode_audio
    except ImportError as exc:
        return False, f"Voice Core: Audio-Abhängigkeit fehlt ({exc})."

    try:
        with tempfile.TemporaryDirectory(prefix="scorpion_mk90_voice_") as tmp:
            wav_path = Path(tmp) / "test_signal.wav"
            sample_rate = 16000
            frames = 3200
            signal = struct.pack(
                "<" + "h" * frames,
                *(int(2000 * math.sin(2 * math.pi * 440 * n / sample_rate))
                  for n in range(frames)),
            )
            with wave.open(str(wav_path), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(sample_rate)
                writer.writeframes(signal)
            decoded = decode_audio(str(wav_path), sampling_rate=sample_rate)
            if len(decoded) != frames:
                return False, "Voice Core: Audiodecoder lieferte eine unerwartete Samplezahl."
    except TypeError as exc:
        if "metadata_errors" in str(exc):
            return False, (
                "Voice Core: PyAV ist inkompatibel mit Faster-Whisper. "
                'Installiere in der MK90-Python-Umgebung "av>=11,<19".'
            )
        return False, f"Voice Core: Decoderfehler ({type(exc).__name__})."
    except Exception as exc:
        return False, f"Voice Core: Decoderfehler ({type(exc).__name__})."

    return True, f"VOICE CORE DECODE OK (PyAV {av.__version__})."


def main() -> int:
    ok, message = check_local_decoder()
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
