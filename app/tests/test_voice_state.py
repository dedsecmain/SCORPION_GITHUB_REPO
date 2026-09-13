from scorpion.voice_state import VoiceSession, VoiceState


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_wake_only_opens_exact_twenty_second_window():
    clock = FakeClock()
    session = VoiceSession(wait_seconds=20.0, clock=clock)
    session.acknowledge_wake(has_trailing_command=False)
    assert session.state is VoiceState.ACKNOWLEDGED
    session.mark_ack_finished()
    assert session.state is VoiceState.WAITING_COMMAND
    clock.advance(19.99)
    assert session.tick() is VoiceState.WAITING_COMMAND
    clock.advance(0.01)
    assert session.tick() is VoiceState.STANDBY


def test_first_speech_stops_wait_timer():
    clock = FakeClock()
    session = VoiceSession(wait_seconds=20.0, clock=clock)
    session.acknowledge_wake(False)
    session.mark_ack_finished()
    clock.advance(10)
    session.first_speech_started()
    assert session.state is VoiceState.LISTENING
    clock.advance(30)
    assert session.tick() is VoiceState.LISTENING


def test_trailing_command_moves_to_thinking_after_ack():
    session = VoiceSession(wait_seconds=20.0)
    session.acknowledge_wake(True)
    session.mark_ack_finished()
    assert session.state is VoiceState.THINKING


def test_speaking_returns_to_standby_when_finished():
    session = VoiceSession()
    session.begin_speaking()
    assert session.state is VoiceState.SPEAKING
    session.speech_finished()
    assert session.state is VoiceState.STANDBY
