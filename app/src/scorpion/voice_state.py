from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class VoiceState(str, Enum):
    STANDBY = "STANDBY"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    WAITING_COMMAND = "WAITING_COMMAND"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VoiceEvent:
    state: VoiceState
    message: str = ""
    remaining: float | None = None


class VoiceSession:
    def __init__(self, wait_seconds: float = 20.0, *, clock: Callable[[], float] | None = None):
        self.wait_seconds = float(wait_seconds)
        self._clock = clock or time.monotonic
        self.state = VoiceState.STANDBY
        self._deadline: float | None = None
        self._wake_has_command = False
        self.last_error = ""

    @property
    def remaining(self) -> float | None:
        if self.state is not VoiceState.WAITING_COMMAND or self._deadline is None:
            return None
        return max(0.0, self._deadline - self._clock())

    def acknowledge_wake(self, has_trailing_command: bool) -> VoiceState:
        self._wake_has_command = bool(has_trailing_command)
        self._deadline = None
        self.state = VoiceState.ACKNOWLEDGED
        return self.state

    def on_wake(self, match) -> VoiceState:
        return self.acknowledge_wake(bool(getattr(match, "trailing_text", "")))

    def mark_ack_finished(self) -> VoiceState:
        if self.state is not VoiceState.ACKNOWLEDGED:
            return self.state
        if self._wake_has_command:
            self.state = VoiceState.THINKING
        else:
            self.state = VoiceState.WAITING_COMMAND
            self._deadline = self._clock() + self.wait_seconds
        return self.state

    def first_speech_started(self) -> VoiceState:
        if self.state in {VoiceState.WAITING_COMMAND, VoiceState.ACKNOWLEDGED}:
            self._deadline = None
            self.state = VoiceState.LISTENING
        return self.state

    def user_started_speaking(self) -> VoiceState:
        """Enter LISTENING when the user talks over Scorpion's own speech."""
        if self.state is VoiceState.SPEAKING:
            self._deadline = None
            self.state = VoiceState.LISTENING
            return self.state
        return self.first_speech_started()

    def on_first_speech(self) -> VoiceState:
        return self.first_speech_started()

    def command_received(self, _text: str = "") -> VoiceState:
        self._deadline = None
        self.state = VoiceState.THINKING
        return self.state

    def on_command(self, text: str) -> VoiceState:
        return self.command_received(text)

    def begin_speaking(self) -> VoiceState:
        self._deadline = None
        self.state = VoiceState.SPEAKING
        return self.state

    def speech_finished(self) -> VoiceState:
        self._deadline = None
        self.state = VoiceState.STANDBY
        return self.state

    def on_speech_finished(self) -> VoiceState:
        return self.speech_finished()

    def fail(self, message: str) -> VoiceState:
        self.last_error = str(message)
        self._deadline = None
        self.state = VoiceState.ERROR
        return self.state

    def on_error(self, message: str) -> VoiceState:
        return self.fail(message)

    def reset(self) -> VoiceState:
        self.last_error = ""
        self._deadline = None
        self._wake_has_command = False
        self.state = VoiceState.STANDBY
        return self.state

    def tick(self, now: float | None = None) -> VoiceState:
        current = self._clock() if now is None else float(now)
        if (
            self.state is VoiceState.WAITING_COMMAND
            and self._deadline is not None
            and current >= self._deadline
        ):
            self.reset()
        return self.state
