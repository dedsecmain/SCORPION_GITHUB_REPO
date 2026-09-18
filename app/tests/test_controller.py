from pathlib import Path

from scorpion.app import ScorpionController
from scorpion.config import Mode, Settings


class FakeLocalAI:
    def __init__(self, answer="local answer"):
        self.answer = answer
        self.calls = []

    def respond(self, text, history=(), image_bytes=None):
        self.calls.append((text, list(history), image_bytes))
        return self.answer

    def status(self):
        class Status:
            state = "ready"
            detail = "OLLAMA READY"
        return Status()


class FakeCloudAI:
    def __init__(self):
        self.calls = []

    def respond(self, token, text, history=(), image_bytes=None):
        self.calls.append((token, text, list(history), image_bytes))
        return "cloud answer"


class FakeScreen:
    def capture_jpeg(self):
        return b"screen-jpeg"


class FakeAudio:
    def __init__(self, transcript="Scorpion, hallo"):
        self.transcript = transcript
        self.record_calls = []

    def record_wav(self, seconds):
        self.record_calls.append(seconds)
        return Path("fake.wav")

    def transcribe(self, _path):
        return self.transcript

    def speak(self, _text):
        return True

    def speech_status(self):
        return "LOCAL SPEECH READY"


class FakeHandoff:
    def build_prompt(self, task, history=(), image_attached=False):
        return f"PROMPT:{task}:{image_attached}:{len(list(history))}"

    def copy_and_open(self, prompt):
        class Result:
            copied = True
            opened = True
            error = None
        result = Result()
        result.prompt = prompt
        return result


def settings(tmp_path: Path, mode=Mode.LOCAL) -> Settings:
    return Settings(
        api_key=None,
        model="gpt-test",
        transcription_model="unused",
        tts_model="unused",
        voice="cedar",
        wake_word="Scorpion",
        memory_path=tmp_path / "memory.json",
        mic_seconds=2,
        wake_listener_seconds=2,
        wake_listener_enabled=False,
        realtime_model="unused",
        mode=mode,
        local_model="gemma3:4b",
        ollama_url="http://127.0.0.1:11434",
        whisper_model="base",
        adaptive_path=tmp_path / "adaptive.json",
        long_term_memory_path=tmp_path / "long_term_memory.json",
        app_trust_path=tmp_path / "app_trust.json",
    )


def make_controller(tmp_path, *, mode=Mode.LOCAL, approval=lambda _reason: False):
    local = FakeLocalAI()
    cloud = FakeCloudAI()
    audio = FakeAudio()
    controller = ScorpionController(
        settings(tmp_path, mode),
        approval_callback=approval,
        local_ai=local,
        local_audio=audio,
        cloud_ai=cloud,
        handoff=FakeHandoff(),
    )
    return controller, local, cloud, audio


def test_controller_routes_screen_request_to_local_vision(tmp_path):
    controller, local, cloud, _audio = make_controller(tmp_path)
    controller.screen = FakeScreen()

    answer = controller.handle("was ist auf meinem bildschirm?")

    assert answer == "local answer"
    assert local.calls[-1][2] == b"screen-jpeg"
    assert cloud.calls == []


def test_plain_local_chat_never_calls_cloud(tmp_path):
    controller, local, cloud, _audio = make_controller(tmp_path)
    assert controller.handle("erklär mir physik") == "local answer"
    assert len(local.calls) == 1
    assert cloud.calls == []


def test_local_voice_and_wake_do_not_require_api_key(tmp_path):
    controller, _local, _cloud, audio = make_controller(tmp_path)

    command, heard = controller.listen_once()
    listener = controller.create_wake_listener(lambda *_args: None)

    assert command == "hallo"
    assert heard == "Scorpion, hallo"
    assert listener is not None
    assert listener.audio is audio


class RoleAwareFakeLocalAI(FakeLocalAI):
    def respond(self, text, history=(), image_bytes=None, *, model=None):
        self.calls.append((text, list(history), image_bytes, model))
        return self.answer


def test_text_and_vision_use_different_selected_models(tmp_path):
    local = RoleAwareFakeLocalAI()
    controller = ScorpionController(
        settings(tmp_path),
        local_ai=local,
        local_audio=FakeAudio(),
        cloud_ai=FakeCloudAI(),
        handoff=FakeHandoff(),
        text_model="qwen3:8b",
        vision_model="gemma3:12b",
    )
    controller.handle("erklär mir quantenverschränkung")
    assert local.calls[-1][3] == "qwen3:8b"
    controller._ask_local("was ist auf meinem bild?", image_bytes=b"jpeg")
    assert local.calls[-1][3] == "gemma3:12b"


def test_first_use_app_approval_trusts_then_executes(tmp_path, monkeypatch):
    controller, _local, _cloud, _audio = make_controller(
        tmp_path,
        approval=lambda _reason: False,
    )
    approvals = []
    controller.action_approval_callback = lambda reason: approvals.append(reason) or True

    monkeypatch.setattr(
        "scorpion.app.execute_windows_action",
        lambda target, trust_registry=None: (True, f"{target} geöffnet."),
    )

    answer = controller.handle("öffne den rechner")

    assert answer == "calculator geöffnet."
    assert approvals and "Erste App-Freigabe" in approvals[0]
    assert controller.app_trust.is_trusted("calc.exe") is True


def test_denied_first_use_app_approval_has_no_side_effect(tmp_path, monkeypatch):
    controller, _local, _cloud, _audio = make_controller(tmp_path)
    controller.action_approval_callback = lambda _reason: False
    calls = []
    monkeypatch.setattr(
        "scorpion.app.execute_windows_action",
        lambda target, trust_registry=None: calls.append(target) or (True, "unexpected"),
    )

    answer = controller.handle("öffne den rechner")

    assert "Freigabe" in answer
    assert calls == []
    assert controller.app_trust.is_trusted("calc.exe") is False
