import asyncio
from pathlib import Path

from scorpion.natural_tts import NaturalVoiceService


def test_natural_voice_synthesizes_then_plays_and_cleans_up(tmp_path):
    events = []

    async def synthesize(text, output_path, voice, rate, pitch, volume):
        events.append(("synth", text, voice, rate, pitch, volume))
        Path(output_path).write_bytes(b"mp3")

    def play(path):
        events.append(("play", Path(path).read_bytes()))

    voice = NaturalVoiceService(
        voice="de-CH-LeniNeural",
        rate="-4%",
        pitch="+0Hz",
        volume="+0%",
        synthesizer=synthesize,
        player=play,
        temp_dir=tmp_path,
    )

    assert voice.speak("Hoi, ich bin Scorpion.") is True
    assert events == [
        ("synth", "Hoi, ich bin Scorpion.", "de-CH-LeniNeural", "-4%", "+0Hz", "+0%"),
        ("play", b"mp3"),
    ]
    assert not list(tmp_path.glob("scorpion_voice_*.mp3"))


def test_natural_voice_returns_false_when_online_synthesis_fails(tmp_path):
    async def broken(*_args, **_kwargs):
        raise RuntimeError("offline")

    voice = NaturalVoiceService(synthesizer=broken, player=lambda _path: None, temp_dir=tmp_path)
    assert voice.speak("Hallo") is False


def test_speech_text_preserves_line_breaks_as_pauses():
    spoken = NaturalVoiceService._speech_text("Erster Satz.\nZweiter Satz.\n\nDritter Satz.")
    assert "Erster Satz., Zweiter Satz." in spoken
    assert "Dritter Satz." in spoken
