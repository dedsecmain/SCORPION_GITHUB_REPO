import time
from pathlib import Path

from scorpion.listener import ContinuousWakeListener
from scorpion.local_audio import SpeechCaptureResult
from scorpion.voice_state import VoiceState


class FakeAudio:
    def __init__(self, transcripts=None, command_text="wie spät ist es"):
        self.calls = 0
        self.transcripts = list(transcripts or ["nur hintergrund", "Scorpion, öffne den Rechner"])
        self.spoken = []
        self.command_text = command_text
        self.capture_calls = []

    def record_wav(self, seconds: float):
        self.calls += 1
        return Path(f"chunk-{self.calls}.wav")

    def transcribe_wake(self, path):
        if self.transcripts:
            return self.transcripts.pop(0)
        return ""

    def transcribe_command(self, path):
        return self.command_text

    def speak(self, text):
        self.spoken.append(text)
        return True

    def capture_until_silence(self, **kwargs):
        self.capture_calls.append(kwargs)
        return SpeechCaptureResult(Path("command.wav"), True, False, 0.4)


def wait_until(predicate, timeout=1.0):
    deadline = time.time() + timeout
    while not predicate() and time.time() < deadline:
        time.sleep(0.01)


def test_listener_dispatches_only_after_wake_phrase_and_silences_background():
    heard = []
    statuses = []
    audio = FakeAudio()
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.01,
        on_command=lambda command, transcript: heard.append((command, transcript)),
        on_status=statuses.append,
    )
    listener.start()
    wait_until(lambda: bool(heard))
    listener.stop()
    assert heard[0][0] == "öffne den Rechner"
    assert audio.spoken == ["Ja, Herr Rodriguez."]
    assert all("wakeword" not in message.lower() for message in statuses)
    assert listener.running is False


def test_wake_only_acknowledges_then_waits_for_command_capture():
    heard = []
    states = []
    audio = FakeAudio(transcripts=["Scorpion"])
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.01,
        on_command=lambda command, transcript: heard.append((command, transcript)),
        on_state=lambda state, remaining=None: states.append((state, remaining)),
        wait_seconds=20.0,
        end_silence_ms=900,
        max_command_seconds=30.0,
    )
    listener.start()
    wait_until(lambda: bool(heard))
    listener.stop()
    assert audio.spoken[0] == "Ja, Herr Rodriguez."
    assert audio.capture_calls[0]["onset_timeout"] == 20.0
    assert audio.capture_calls[0]["end_silence_ms"] == 900
    assert audio.capture_calls[0]["max_seconds"] == 30.0
    assert heard[0][0] == "wie spät ist es"
    assert any(state is VoiceState.WAITING_COMMAND for state, _ in states)
    assert any(state is VoiceState.LISTENING for state, _ in states)


def test_wake_only_times_out_silently():
    class TimeoutAudio(FakeAudio):
        def capture_until_silence(self, **kwargs):
            self.capture_calls.append(kwargs)
            return SpeechCaptureResult(None, False, True, 0.0)

    heard = []
    audio = TimeoutAudio(transcripts=["Scorpion"])
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.01,
        on_command=lambda *args: heard.append(args),
        wait_seconds=20.0,
    )
    listener.start()
    wait_until(lambda: bool(audio.capture_calls))
    time.sleep(0.03)
    listener.stop()
    assert heard == []



def test_wake_listener_recovers_after_transient_audio_failure():
    class FlakyAudio(FakeAudio):
        def __init__(self):
            super().__init__(transcripts=["Scorpion, status"])
            self.record_attempts = 0

        def record_wav(self, seconds: float):
            self.record_attempts += 1
            if self.record_attempts == 1:
                raise OSError("temporary microphone failure")
            return Path("recovered.wav")

    heard = []
    statuses = []
    audio = FlakyAudio()
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.01,
        on_command=lambda command, transcript: heard.append((command, transcript)),
        on_status=statuses.append,
        recovery_delay=0.01,
        max_recovery_delay=0.02,
    )
    listener.start()
    wait_until(lambda: bool(heard), timeout=1.0)
    assert heard and heard[0][0] == "status"
    assert any(status.startswith("RECOVERING") for status in statuses)
    assert listener.running is True
    listener.stop()
