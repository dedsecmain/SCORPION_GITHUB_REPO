from pathlib import Path
import wave

import pytest

from scorpion.local_audio import LocalAudioService, LocalSpeechUnavailableError, SpeechCaptureResult


def test_record_wav_uses_standard_wav_container(tmp_path):
    pcm = (b"\x01\x00" * 160)
    calls = []

    def recorder(seconds, sample_rate):
        calls.append((seconds, sample_rate))
        return pcm

    audio = LocalAudioService("base", recorder=recorder, temp_dir=tmp_path)
    path = audio.record_wav(0.01, sample_rate=16000)

    assert path.exists()
    assert calls == [(0.01, 16000)]
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.readframes(160) == pcm


def test_whisper_model_is_loaded_lazily_and_reused(tmp_path):
    model_creations = []

    class Segment:
        def __init__(self, text):
            self.text = text

    class FakeModel:
        def transcribe(self, path, **kwargs):
            assert Path(path).name == "voice.wav"
            return [Segment(" hallo"), Segment(" welt ")], object()

    def whisper_factory(model_name):
        model_creations.append(model_name)
        return FakeModel()

    audio = LocalAudioService("base", whisper_factory=whisper_factory, temp_dir=tmp_path)
    assert model_creations == []

    source = tmp_path / "voice.wav"
    source.write_bytes(b"not-used-by-fake")
    assert audio.transcribe(source) == "hallo welt"
    assert audio.transcribe(source) == "hallo welt"
    assert model_creations == ["base"]


def test_missing_whisper_is_reported_without_breaking_text_chat(tmp_path):
    def missing(_name):
        raise ImportError("no faster whisper")

    audio = LocalAudioService("base", whisper_factory=missing, temp_dir=tmp_path)
    source = tmp_path / "voice.wav"
    source.write_bytes(b"x")

    with pytest.raises(LocalSpeechUnavailableError, match="faster-whisper"):
        audio.transcribe(source)


def test_missing_local_tts_returns_false():
    def missing_tts():
        raise ImportError("no tts")

    audio = LocalAudioService("base", tts_factory=missing_tts)
    assert audio.speak("hallo") is False


def test_natural_voice_is_preferred_over_offline_fallback():
    calls = []

    class Natural:
        def speak(self, text):
            calls.append(("natural", text))
            return True

    class Offline:
        def say(self, text):
            calls.append(("offline-say", text))

        def runAndWait(self):
            calls.append(("offline-run", None))

    audio = LocalAudioService(
        "base",
        natural_tts_factory=lambda: Natural(),
        tts_factory=lambda: Offline(),
    )

    assert audio.speak("Hallo") is True
    assert calls == [("natural", "Hallo")]


def test_offline_tts_is_used_when_natural_voice_fails():
    calls = []

    class Natural:
        def speak(self, text):
            calls.append(("natural", text))
            return False

    class Offline:
        def say(self, text):
            calls.append(("offline-say", text))

        def runAndWait(self):
            calls.append(("offline-run", None))

    audio = LocalAudioService(
        "base",
        natural_tts_factory=lambda: Natural(),
        tts_factory=lambda: Offline(),
    )

    assert audio.speak("Hallo") is True
    assert calls == [
        ("natural", "Hallo"),
        ("offline-say", "Hallo"),
        ("offline-run", None),
    ]


def test_dual_whisper_profiles_are_cached_independently(tmp_path):
    created = []

    class Segment:
        text = " hallo "

    class FakeModel:
        def transcribe(self, path, **kwargs):
            return [Segment()], object()

    def factory(name):
        created.append(name)
        return FakeModel()

    audio = LocalAudioService(
        "base",
        wake_whisper_model="tiny",
        command_whisper_model="small",
        whisper_factory=factory,
        temp_dir=tmp_path,
    )
    source = tmp_path / "voice.wav"
    source.write_bytes(b"x")
    assert audio.transcribe_wake(source) == "hallo"
    assert audio.transcribe_wake(source) == "hallo"
    assert audio.transcribe_command(source) == "hallo"
    assert created == ["tiny", "small"]


def test_capture_wake_segment_uses_vad_capture_settings(monkeypatch):
    audio = LocalAudioService("base")
    calls = []
    expected = SpeechCaptureResult(None, False, True, 0.0)
    monkeypatch.setattr(audio, "capture_until_silence", lambda **kwargs: calls.append(kwargs) or expected)
    assert audio.capture_wake_segment(onset_timeout=1.75) is expected
    assert calls == [{"onset_timeout": 1.75, "end_silence_ms": 450, "max_seconds": 3.5}]



def test_command_transcription_carries_high_german_prompt(tmp_path):
    captured = {}

    class Segment:
        text = " öffne github "

    class FakeModel:
        def transcribe(self, path, **kwargs):
            captured.update(kwargs)
            return [Segment()], object()

    audio = LocalAudioService(
        "base",
        command_whisper_model="small",
        whisper_factory=lambda _name: FakeModel(),
        temp_dir=tmp_path,
    )
    source = tmp_path / "voice.wav"
    source.write_bytes(b"x")
    assert audio.transcribe_command(source) == "öffne github"
    assert "Hochdeutscher Befehl" in captured["initial_prompt"]



def test_voice_core_reports_usable_input_device(monkeypatch):
    import sys
    from types import SimpleNamespace

    checks = []
    fake = SimpleNamespace(
        query_devices=lambda kind: {"name": "Microphone", "max_input_channels": 2},
        check_input_settings=lambda **kwargs: checks.append(kwargs),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    ok, status = LocalAudioService.microphone_status()
    assert ok is True
    assert "Microphone" in status
    assert checks == [{"channels": 1, "samplerate": 16000, "dtype": "int16"}]


def test_voice_core_reports_missing_microphone_without_crashing(monkeypatch):
    import sys
    from types import SimpleNamespace

    def unavailable(**_kwargs):
        raise OSError("device busy")

    fake = SimpleNamespace(
        query_devices=lambda kind: {"name": "Busy microphone", "max_input_channels": 1},
        check_input_settings=unavailable,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    ok, status = LocalAudioService.microphone_status()
    assert ok is False
    assert "Mikrofon" in status
    assert "Windows" in status



def test_metadata_errors_pyav_19_failure_has_actionable_voice_core_fix(tmp_path):
    class IncompatibleWhisper:
        def transcribe(self, _path, **kwargs):
            raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    audio = LocalAudioService(
        "base", whisper_factory=lambda _model: IncompatibleWhisper(),
        temp_dir=tmp_path,
    )
    source = tmp_path / "voice.wav"
    source.write_bytes(b"example audio")
    with pytest.raises(LocalSpeechUnavailableError) as captured:
        audio.transcribe_command(source)

    message = str(captured.value)
    assert "Voice Core" in message
    assert "PyAV" in message
    assert "av>=11,<19" in message
    assert "Mikrofonaufnahme" not in message


def test_other_transcription_errors_keep_existing_diagnostics(tmp_path):
    class BrokenWhisper:
        def transcribe(self, _path, **kwargs):
            raise ValueError("corrupted audio")

    audio = LocalAudioService(
        "base", whisper_factory=lambda _model: BrokenWhisper(),
        temp_dir=tmp_path,
    )
    source = tmp_path / "voice.wav"
    source.write_bytes(b"example audio")
    with pytest.raises(LocalSpeechUnavailableError, match="corrupted audio"):
        audio.transcribe_command(source)



def test_voice_output_recovers_with_offline_windows_speaker():
    spoken = []

    class NoNetwork:
        last_error = "ConnectionError"

        def speak(self, _text):
            return False

    class ShouldNotUsePyttsx:
        def __init__(self):
            raise AssertionError("SAPI succeeded so pyttsx3 must not run")

    audio = LocalAudioService(
        natural_tts_factory=lambda: NoNetwork(),
        offline_speaker=lambda text: spoken.append(text),
        tts_factory=ShouldNotUsePyttsx,
    )
    audio._prefer_windows_sapi = True
    assert audio.speak("Hallo, ich bin Scorpion.") is True
    assert spoken == ["Hallo, ich bin Scorpion."]
    assert audio.last_tts_engine == "WINDOWS OFFLINE"
    assert audio.last_tts_error is None


def test_voice_output_reports_failure_when_all_engines_fail():
    def bad_sapi(_text):
        raise RuntimeError("Output device unavailable")

    def bad_pyttsx():
        raise RuntimeError("SAPI not registered")

    audio = LocalAudioService(
        natural_voice_enabled=False,
        offline_speaker=bad_sapi,
        tts_factory=bad_pyttsx,
    )
    audio._prefer_windows_sapi = True
    assert audio.speak("Hallo") is False
    assert audio.last_tts_engine is None
    assert "Windows-Stimme" in audio.last_tts_error
    assert "pyttsx3" in audio.last_tts_error


def test_voice_output_exposes_engine_selected_for_offline_fallback():
    class Fallback:
        def say(self, text):
            assert text == "Hallo"

        def runAndWait(self):
            pass

    audio = LocalAudioService(
        natural_voice_enabled=False,
        tts_factory=lambda: Fallback(),
    )
    assert audio.speak("Hallo") is True
    assert audio.last_tts_engine == "PYTTSX3 OFFLINE"
