from __future__ import annotations

import tempfile
from pathlib import Path


class AudioService:
    def __init__(self, api_key: str, transcription_model: str, tts_model: str, voice: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.transcription_model = transcription_model
        self.tts_model = tts_model
        self.voice = voice

    def record_wav(self, seconds: float = 6.0, sample_rate: int = 16000) -> Path:
        import sounddevice as sd
        from scipy.io.wavfile import write

        frames = int(seconds * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        path = Path(tempfile.gettempdir()) / "scorpion_input.wav"
        write(path, sample_rate, audio)
        return path

    def transcribe(self, path: Path) -> str:
        with path.open("rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model=self.transcription_model,
                file=audio_file,
            )
        return transcript.text.strip()

    def speak(self, text: str) -> Path:
        output = Path(tempfile.gettempdir()) / "scorpion_voice.wav"
        with self.client.audio.speech.with_streaming_response.create(
            model=self.tts_model,
            voice=self.voice,
            input=text[:4096],
            instructions="Confident, calm, witty personal AI assistant. Natural German pronunciation when speaking German.",
            response_format="wav",
        ) as response:
            response.stream_to_file(output)

        try:
            import winsound

            winsound.PlaySound(str(output), winsound.SND_FILENAME)
        except ImportError:
            pass
        return output
