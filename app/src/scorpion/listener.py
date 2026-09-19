from __future__ import annotations

import re
import threading
from collections.abc import Callable

from .voice_state import VoiceSession, VoiceState
from .wake_matcher import WakeMatcher


ACK_TEXT = "Ja, Herr Rodriguez."


def _speech_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZäöüÄÖÜß0-9]+", text.lower()))


class ContinuousWakeListener:
    def __init__(
        self,
        audio,
        wake_word: str,
        chunk_seconds: float,
        on_command: Callable[[str, str], None],
        on_status: Callable[[str], None] | None = None,
        *,
        on_state: Callable[[VoiceState, float | None], None] | None = None,
        wait_seconds: float = 20.0,
        end_silence_ms: int = 900,
        max_command_seconds: float = 30.0,
        aliases: set[str] | None = None,
        recovery_delay: float = 0.35,
        max_recovery_delay: float = 3.0,
    ):
        self.audio = audio
        self.wake_word = wake_word
        self.chunk_seconds = max(0.01, float(chunk_seconds))
        self.on_command = on_command
        self.on_status = on_status or (lambda _text: None)
        self.on_state = on_state or (lambda _state, _remaining=None: None)
        self.wait_seconds = float(wait_seconds)
        self.end_silence_ms = int(end_silence_ms)
        self.max_command_seconds = float(max_command_seconds)
        self.matcher = WakeMatcher(wake_word, aliases=aliases)
        self.session = VoiceSession(wait_seconds=self.wait_seconds)
        self.recovery_delay = max(0.01, float(recovery_delay))
        self.max_recovery_delay = max(self.recovery_delay, float(max_recovery_delay))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._assistant_speech_text = ""
        register = getattr(self.audio, "set_barge_in_listener", None)
        if callable(register):
            register(self)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def _emit_state(self) -> None:
        self.on_state(self.session.state, self.session.remaining)
        self.on_status(self.session.state.value)

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="scorpion-wake-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=max(0.2, min(self.chunk_seconds + 0.5, 2.0)))
        self._thread = None

    def _transcribe_wake(self, path) -> str:
        method = getattr(self.audio, "transcribe_wake", None) or getattr(self.audio, "transcribe")
        return method(path).strip()

    def _transcribe_command(self, path) -> str:
        method = getattr(self.audio, "transcribe_command", None) or getattr(self.audio, "transcribe")
        return method(path).strip()

    def _acknowledge(self, has_trailing_command: bool) -> None:
        self.session.acknowledge_wake(has_trailing_command)
        self._emit_state()
        try:
            self.audio.speak(ACK_TEXT, allow_barge_in=False)
        except TypeError:
            self.audio.speak(ACK_TEXT)
        self.session.mark_ack_finished()
        self._emit_state()

    def begin_assistant_speech(self, text: str) -> None:
        self._assistant_speech_text = text.strip()
        self.session.begin_speaking()
        self._emit_state()

    def end_assistant_speech(self) -> None:
        self._assistant_speech_text = ""
        if self.session.state is VoiceState.SPEAKING:
            self.session.speech_finished()
            self._emit_state()

    def _looks_like_assistant_echo(self, transcript: str) -> bool:
        heard = _speech_tokens(transcript)
        spoken = _speech_tokens(self._assistant_speech_text)
        if not heard or not spoken:
            return False
        overlap = len(heard & spoken) / max(1, len(heard))
        return overlap >= 0.75

    def interrupt_speaking(self) -> bool:
        if self.session.state is not VoiceState.SPEAKING:
            return False
        stopper = getattr(self.audio, "stop", None)
        if callable(stopper):
            stopper()
        self.session.user_started_speaking()
        self._emit_state()
        return True

    def _handle_speaking_transcript(self, transcript: str) -> bool:
        transcript = transcript.strip()
        if not transcript:
            return False
        if self._looks_like_assistant_echo(transcript):
            return True
        if not self.interrupt_speaking():
            return False
        self.session.command_received(transcript)
        self._emit_state()
        self.on_command(transcript, transcript)
        self.session.reset()
        self._assistant_speech_text = ""
        self._emit_state()
        return True

    def _handle_transcript(self, transcript: str) -> bool:
        if self.session.state is VoiceState.SPEAKING:
            return self._handle_speaking_transcript(transcript)

        match = self.matcher.match(transcript)
        if match is None:
            return False

        trailing = match.trailing_text.strip()
        self._acknowledge(bool(trailing))
        if trailing:
            self.on_command(trailing, transcript)
            self.session.reset()
            self._emit_state()
            return True

        capture_method = getattr(self.audio, "capture_until_silence", None)
        if capture_method is None:
            self.session.reset()
            self._emit_state()
            return True

        def on_speech_start() -> None:
            self.session.first_speech_started()
            self._emit_state()

        result = capture_method(
            onset_timeout=self.wait_seconds,
            end_silence_ms=self.end_silence_ms,
            max_seconds=self.max_command_seconds,
            on_speech_start=on_speech_start,
        )
        if self._stop.is_set():
            return True
        if not result.speech_detected or result.path is None:
            self.session.reset()
            self._emit_state()
            return True

        if self.session.state is not VoiceState.LISTENING:
            self.session.first_speech_started()
            self._emit_state()
        command = self._transcribe_command(result.path)
        if command:
            self.session.command_received(command)
            self._emit_state()
            self.on_command(command, command)
        self.session.reset()
        self._emit_state()
        return True

    def feed_transcript(self, transcript: str) -> bool:
        return self._handle_transcript(transcript)

    def _run(self) -> None:
        self.session.reset()
        self._emit_state()
        consecutive_errors = 0
        try:
            while not self._stop.is_set():
                try:
                    wake_capture = getattr(self.audio, "capture_wake_segment", None)
                    if wake_capture is not None:
                        result = wake_capture(onset_timeout=self.chunk_seconds)
                        if self._stop.is_set():
                            break
                        if not result.speech_detected or result.path is None:
                            consecutive_errors = 0
                            continue
                        path = result.path
                    else:
                        path = self.audio.record_wav(self.chunk_seconds)
                        if self._stop.is_set():
                            break

                    if self.session.state is VoiceState.SPEAKING:
                        transcript = self._transcribe_command(path)
                    else:
                        transcript = self._transcribe_wake(path)
                    if transcript:
                        self._handle_transcript(transcript)
                    consecutive_errors = 0
                    self._stop.wait(0.03)
                except Exception as exc:
                    if self._stop.is_set():
                        break
                    consecutive_errors += 1
                    self.session.fail(str(exc))
                    self._emit_state()
                    self.on_status(f"RECOVERING · {exc}")
                    delay = min(
                        self.max_recovery_delay,
                        self.recovery_delay * (2 ** min(consecutive_errors - 1, 4)),
                    )
                    if self._stop.wait(delay):
                        break
                    self.session.reset()
                    self._emit_state()
        finally:
            self._stop.set()
            self.on_status("OFF")
