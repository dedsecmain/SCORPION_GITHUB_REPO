from scorpion.listener import ContinuousWakeListener
from scorpion.voice_state import VoiceSession, VoiceState


class InterruptibleAudio:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1

    def speak(self, _text):
        return True


def test_user_speech_interrupts_speaking_into_listening():
    session = VoiceSession()
    session.begin_speaking()
    assert session.user_started_speaking() is VoiceState.LISTENING
    assert session.state is VoiceState.LISTENING


def test_listener_barge_in_stops_speaker_once_and_dispatches_command():
    heard = []
    audio = InterruptibleAudio()
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.1,
        on_command=lambda command, transcript: heard.append((command, transcript)),
    )
    listener.begin_assistant_speech("Ich öffne jetzt den Explorer und zeige dir die Dateien.")

    handled = listener.feed_transcript("Stopp, öffne lieber den Rechner")

    assert handled is True
    assert audio.stop_calls == 1
    assert heard == [("Stopp, öffne lieber den Rechner", "Stopp, öffne lieber den Rechner")]
    assert listener.session.state is VoiceState.STANDBY


def test_listener_ignores_echo_of_its_own_spoken_text():
    heard = []
    audio = InterruptibleAudio()
    listener = ContinuousWakeListener(
        audio=audio,
        wake_word="Scorpion",
        chunk_seconds=0.1,
        on_command=lambda command, transcript: heard.append((command, transcript)),
    )
    listener.begin_assistant_speech("Das Wetter ist heute sonnig und warm.")

    handled = listener.feed_transcript("Das Wetter ist heute sonnig und warm")

    assert handled is True
    assert audio.stop_calls == 0
    assert heard == []
    assert listener.session.state is VoiceState.SPEAKING
