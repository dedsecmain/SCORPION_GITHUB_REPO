from __future__ import annotations

import importlib.util
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .vad import VADSegmenter, VADUnavailableError


class LocalSpeechUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeechCaptureResult:
    path: Path | None
    speech_detected: bool
    timed_out: bool
    mic_level: float = 0.0


class LocalAudioService:
    def __init__(
        self,
        whisper_model: str = "base",
        *,
        wake_whisper_model: str | None = None,
        command_whisper_model: str | None = None,
        vad_aggressiveness: int = 2,
        recorder: Callable[[float, int], bytes] | None = None,
        whisper_factory: Callable[[str], object] | None = None,
        tts_factory: Callable[[], object] | None = None,
        natural_tts_factory: Callable[[], object] | None = None,
        natural_voice: str = "de-CH-LeniNeural",
        natural_voice_rate: str = "-4%",
        natural_voice_pitch: str = "+0Hz",
        natural_voice_enabled: bool = True,
        temp_dir: Path | str | None = None,
        stream_factory=None,
        clock: Callable[[], float] | None = None,
    ):
        self.whisper_model = whisper_model
        self.wake_whisper_model = wake_whisper_model or whisper_model
        requested_command = command_whisper_model or whisper_model
        self.command_whisper_model = whisper_model if requested_command == "auto" else requested_command
        self.vad_aggressiveness = int(vad_aggressiveness)
        self._recorder = recorder or self._record_pcm_default
        self._whisper_factory = whisper_factory or self._default_whisper_factory
        self._tts_factory = tts_factory or self._default_tts_factory
        self.natural_voice_enabled = bool(natural_voice_enabled)
        self._natural_tts_factory = natural_tts_factory or (
            lambda: self._default_natural_tts_factory(
                natural_voice, natural_voice_rate, natural_voice_pitch
            )
        )
        self._natural_tts = None
        self._whispers: dict[str, object] = {}
        self.temp_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
        self._stream_factory = stream_factory
        self._clock = clock or time.monotonic

    @staticmethod
    def _record_pcm_default(seconds: float, sample_rate: int) -> bytes:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise LocalSpeechUnavailableError(
                "sounddevice fehlt. Führe setup_scorpion.bat erneut aus."
            ) from exc

        frames = max(1, int(seconds * sample_rate))
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        return audio.tobytes()

    @staticmethod
    def _default_whisper_factory(model_name: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise LocalSpeechUnavailableError(
                "faster-whisper fehlt. Führe setup_scorpion.bat erneut aus."
            ) from exc
        return WhisperModel(model_name, device="cpu", compute_type="int8")

    @staticmethod
    def _default_tts_factory():
        import pyttsx3

        return pyttsx3.init()

    @staticmethod
    def _default_natural_tts_factory(voice: str, rate: str, pitch: str):
        from .natural_tts import NaturalVoiceService

        return NaturalVoiceService(voice=voice, rate=rate, pitch=pitch)

    def set_command_whisper_model(self, model_name: str) -> None:
        if model_name and model_name != "auto":
            self.command_whisper_model = model_name

    def _write_wav(self, pcm: bytes, sample_rate: int = 16000, *, prefix: str = "scorpion_input_") -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix=".wav",
            dir=self.temp_dir,
            delete=False,
        ) as tmp:
            path = Path(tmp.name)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(int(sample_rate))
            wav.writeframes(bytes(pcm))
        return path

    def record_wav(self, seconds: float = 6.0, sample_rate: int = 16000) -> Path:
        pcm = self._recorder(float(seconds), int(sample_rate))
        if not isinstance(pcm, (bytes, bytearray, memoryview)):
            try:
                pcm = pcm.tobytes()
            except AttributeError as exc:
                raise LocalSpeechUnavailableError("Mikrofon lieferte ein unbekanntes Audioformat.") from exc
        return self._write_wav(bytes(pcm), int(sample_rate))

    def _get_whisper(self, model_name: str):
        if model_name not in self._whispers:
            try:
                self._whispers[model_name] = self._whisper_factory(model_name)
            except LocalSpeechUnavailableError:
                raise
            except ImportError as exc:
                raise LocalSpeechUnavailableError(
                    "faster-whisper ist nicht verfügbar. Führe setup_scorpion.bat erneut aus."
                ) from exc
            except Exception as exc:
                raise LocalSpeechUnavailableError(
                    f"Lokales Whisper-Modell konnte nicht geladen werden: {exc}"
                ) from exc
        return self._whispers[model_name]

    def _transcribe_with(self, path: Path, model_name: str, *, beam_size: int, initial_prompt: str | None = None) -> str:
        model = self._get_whisper(model_name)
        try:
            kwargs = {"beam_size": int(beam_size), "vad_filter": True}
            if initial_prompt:
                kwargs["initial_prompt"] = initial_prompt
            try:
                segments, _info = model.transcribe(str(path), **kwargs)
            except TypeError:
                kwargs.pop("initial_prompt", None)
                segments, _info = model.transcribe(str(path), **kwargs)
            text = " ".join(
                segment.text.strip()
                for segment in segments
                if getattr(segment, "text", "").strip()
            )
        except Exception as exc:
            raise LocalSpeechUnavailableError(f"Lokale Transkription fehlgeschlagen: {exc}") from exc
        return text.strip()

    def transcribe(self, path: Path) -> str:
        return self._transcribe_with(path, self.whisper_model, beam_size=1)

    def transcribe_wake(self, path: Path) -> str:
        return self._transcribe_with(
            path,
            self.wake_whisper_model,
            beam_size=3,
            initial_prompt="Scorpion. Skorpion. Scorpian. Herr Rodriguez.",
        )

    def transcribe_command(self, path: Path) -> str:
        return self._transcribe_with(path, self.command_whisper_model, beam_size=5)

    def capture_wake_segment(self, *, onset_timeout: float = 2.0) -> SpeechCaptureResult:
        return self.capture_until_silence(
            onset_timeout=onset_timeout,
            end_silence_ms=450,
            max_seconds=3.5,
        )

    def _open_raw_stream(self, sample_rate: int, frame_samples: int):
        if self._stream_factory is not None:
            return self._stream_factory(sample_rate, frame_samples)
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise LocalSpeechUnavailableError(
                "sounddevice fehlt. Führe setup_scorpion.bat erneut aus."
            ) from exc
        return sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=frame_samples,
            channels=1,
            dtype="int16",
        )

    def capture_until_silence(
        self,
        *,
        onset_timeout: float = 20.0,
        end_silence_ms: int = 900,
        max_seconds: float = 30.0,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        on_level: Callable[[float], None] | None = None,
        on_speech_start: Callable[[], None] | None = None,
    ) -> SpeechCaptureResult:
        try:
            vad = VADSegmenter(
                sample_rate=sample_rate,
                frame_ms=frame_ms,
                aggressiveness=self.vad_aggressiveness,
            )
        except (VADUnavailableError, ValueError) as exc:
            raise LocalSpeechUnavailableError(str(exc)) from exc

        frame_samples = vad.frame_samples
        speech_started = False
        started_at = self._clock()
        speech_started_at: float | None = None
        silence_ms = 0
        pcm_parts: list[bytes] = []
        max_level = 0.0

        try:
            stream = self._open_raw_stream(sample_rate, frame_samples)
            with stream:
                while True:
                    now = self._clock()
                    if not speech_started and now - started_at >= float(onset_timeout):
                        return SpeechCaptureResult(None, False, True, max_level)
                    if speech_started and speech_started_at is not None and now - speech_started_at >= float(max_seconds):
                        break

                    data, _overflowed = stream.read(frame_samples)
                    frame = bytes(data)
                    if len(frame) != vad.frame_bytes:
                        continue
                    level = vad.rms_level(frame)
                    max_level = max(max_level, level)
                    if on_level:
                        on_level(level)
                    is_speech = vad.is_speech(frame)

                    if not speech_started:
                        if not is_speech:
                            continue
                        speech_started = True
                        speech_started_at = now
                        if on_speech_start:
                            on_speech_start()
                        pcm_parts.append(frame)
                        silence_ms = 0
                        continue

                    pcm_parts.append(frame)
                    if is_speech:
                        silence_ms = 0
                    else:
                        silence_ms += frame_ms
                        if silence_ms >= int(end_silence_ms):
                            break
        except LocalSpeechUnavailableError:
            raise
        except Exception as exc:
            raise LocalSpeechUnavailableError(f"Mikrofonaufnahme fehlgeschlagen: {exc}") from exc

        if not pcm_parts:
            return SpeechCaptureResult(None, False, True, max_level)
        path = self._write_wav(b"".join(pcm_parts), sample_rate, prefix="scorpion_command_")
        return SpeechCaptureResult(path, True, False, max_level)

    def speak(self, text: str) -> bool:
        if self.natural_voice_enabled:
            try:
                if self._natural_tts is None:
                    self._natural_tts = self._natural_tts_factory()
                if self._natural_tts.speak(text[:6000]):
                    return True
            except Exception:
                pass

        try:
            engine = self._tts_factory()
            engine.say(text[:6000])
            engine.runAndWait()
            return True
        except Exception:
            return False

    def speech_status(self) -> str:
        whisper_ok = importlib.util.find_spec("faster_whisper") is not None
        neural_ok = self.natural_voice_enabled and importlib.util.find_spec("edge_tts") is not None
        tts_ok = importlib.util.find_spec("pyttsx3") is not None
        if whisper_ok and neural_ok:
            return "LOCAL STT · NATURAL VOICE"
        if whisper_ok and tts_ok:
            return "LOCAL STT · OFFLINE VOICE"
        if whisper_ok:
            return "LOCAL STT READY · TTS OFF"
        return "LOCAL SPEECH SETUP NEEDED"
