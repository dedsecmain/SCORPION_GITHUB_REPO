from __future__ import annotations

import asyncio
import base64
import threading
from collections.abc import Callable


def build_realtime_session(
    voice: str,
    instructions: str,
    transcription_model: str = "gpt-4o-mini-transcribe",
) -> dict:
    return {
        "type": "realtime",
        "output_modalities": ["audio"],
        "instructions": instructions,
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "transcription": {"model": transcription_model},
                "turn_detection": {"type": "server_vad"},
                "noise_reduction": {"type": "far_field"},
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "voice": voice,
            },
        },
    }


def realtime_available() -> bool:
    try:
        from openai import AsyncOpenAI  # noqa: F401
        import websockets  # noqa: F401
        import sounddevice  # noqa: F401
    except ImportError:
        return False
    return True


class RealtimeVoiceSession:
    """Low-latency duplex voice session backed by the OpenAI Realtime API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        voice: str,
        instructions: str,
        transcription_model: str,
        on_transcript: Callable[[str, str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.transcription_model = transcription_model
        self.on_transcript = on_transcript or (lambda _who, _text: None)
        self.on_status = on_status or (lambda _text: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="scorpion-realtime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self.on_status(f"ERROR: {exc}")
        finally:
            self._stop.set()
            self.on_status("OFF")

    async def _run(self) -> None:
        from openai import AsyncOpenAI
        import sounddevice as sd

        self.on_status("CONNECTING")
        client = AsyncOpenAI(api_key=self.api_key)
        async with client.realtime.connect(model=self.model) as connection:
            await connection.session.update(
                session=build_realtime_session(self.voice, self.instructions, self.transcription_model)
            )
            self.on_status("LIVE")

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)

            def offer(data: bytes) -> None:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass

            def input_callback(indata, _frames, _time_info, status) -> None:
                if status:
                    self.on_status(f"MIC: {status}")
                if not self._stop.is_set():
                    loop.call_soon_threadsafe(offer, bytes(indata))

            input_stream = sd.RawInputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                blocksize=480,
                callback=input_callback,
            )
            output_stream = sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                blocksize=480,
            )
            input_stream.start()
            output_stream.start()

            async def sender() -> None:
                while not self._stop.is_set():
                    try:
                        chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                    except TimeoutError:
                        continue
                    await connection.input_audio_buffer.append(
                        audio=base64.b64encode(chunk).decode("ascii")
                    )

            sender_task = asyncio.create_task(sender())
            assistant_text: dict[str, str] = {}
            try:
                async for event in connection:
                    if self._stop.is_set():
                        break
                    if event.type == "response.output_audio.delta":
                        output_stream.write(base64.b64decode(event.delta))
                    elif event.type == "response.output_audio_transcript.delta":
                        item_id = getattr(event, "item_id", "assistant")
                        assistant_text[item_id] = assistant_text.get(item_id, "") + event.delta
                    elif event.type == "response.output_audio_transcript.done":
                        item_id = getattr(event, "item_id", "assistant")
                        text = assistant_text.pop(item_id, "").strip()
                        if text:
                            self.on_transcript("SCORPION", text)
                    elif event.type == "conversation.item.input_audio_transcription.completed":
                        text = getattr(event, "transcript", "").strip()
                        if text:
                            self.on_transcript("DU", text)
                    elif event.type == "error":
                        message = getattr(getattr(event, "error", None), "message", "Realtime-Fehler")
                        self.on_status(f"ERROR: {message}")
            finally:
                sender_task.cancel()
                await asyncio.gather(sender_task, return_exceptions=True)
                input_stream.stop()
                output_stream.stop()
                input_stream.close()
                output_stream.close()
