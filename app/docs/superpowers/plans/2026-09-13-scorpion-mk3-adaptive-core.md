# Scorpion Mk III Adaptive Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Scorpion Mk II.1 into Mk III with reliable wake acknowledgement, a 20-second command window, VAD-based speech capture, hardware-aware local model selection, safe adaptive learning, a polished command-center HUD, and confirmation-gated signed GitHub Release updates with rollback.

**Architecture:** Voice input becomes an explicit state machine fed by WebRTC VAD and two local Whisper profiles. Local reasoning is split into hardware/model selection, adaptive settings, and role-based text/vision routing. The desktop UI observes controller state instead of owning voice logic, while update installation is isolated behind signed manifests, a helper process, self-check, backup, and rollback.

**Tech Stack:** Python 3.11+, CustomTkinter, sounddevice, faster-whisper, webrtcvad-wheels, psutil, Ollama localhost HTTP API, edge-tts with pyttsx3 fallback, cryptography Ed25519 verification, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-scorpion-mk3-adaptive-core-design.md`

## Global Constraints

- Local-first remains the default; no OpenAI API traffic from wake, transcription, ordinary local chat, adaptive tuning, update checks, or normal TTS.
- Direct OpenAI API use remains gated by the existing one-use CloudGate approval immediately before each request.
- Wake acknowledgement text is exactly `Ja, Herr Rodriguez.`.
- Wake-only mode waits exactly 20.0 seconds for first speech, then records until configured end silence or a 30-second hard cap.
- Non-wake speech/background noise in STANDBY is discarded silently.
- Adaptive learning may change approved configuration only; it must never rewrite or execute arbitrary code.
- Core/model downloads and update installation require explicit user confirmation.
- No arbitrary shell, PowerShell, browser scraping, coordinate clicking, or unrestricted keyboard/mouse automation.
- Existing `.env`, memory, adaptive settings, Ollama models, and Whisper caches must survive migration/update.

---

### Task 1: Wake matcher and voice state machine

**Files:**
- Create: `src/scorpion/wake_matcher.py`
- Create: `src/scorpion/voice_state.py`
- Create: `tests/test_wake_matcher.py`
- Create: `tests/test_voice_state.py`
- Modify: `src/scorpion/config.py`

**Interfaces:**
- Produces: `WakeMatch`, `WakeMatcher.match(text)`, `VoiceState`, `VoiceSession`, `VoiceEvent`.
- `WakeMatcher.match(text)` returns canonical match metadata plus trailing command without calling any network service.
- `VoiceSession.on_wake(match)`, `on_first_speech()`, `on_command(text)`, `on_speech_finished()`, `on_error(message)`, and `tick(now)` expose deterministic transitions for controller/UI tests.

- [ ] **Step 1: Write failing matcher tests**

```python
from scorpion.wake_matcher import WakeMatcher


def test_accepts_canonical_variant_and_trailing_command():
    matcher = WakeMatcher("Scorpion", aliases={"skorpion", "scorpian"})
    assert matcher.match("Skorpion, öffne den Rechner").trailing_text == "öffne den Rechner"


def test_rejects_unrelated_fuzzy_word():
    matcher = WakeMatcher("Scorpion", aliases=set(), max_edit_distance=2)
    assert matcher.match("skulpturen sind schön") is None
```

- [ ] **Step 2: Run matcher tests and verify RED**

```bash
pytest -q tests/test_wake_matcher.py
```

Expected: import failure because `scorpion.wake_matcher` does not yet exist.

- [ ] **Step 3: Implement deterministic WakeMatcher**

```python
@dataclass(frozen=True)
class WakeMatch:
    matched_text: str
    normalized_alias: str
    trailing_text: str

class WakeMatcher:
    def match(self, text: str) -> WakeMatch | None:
        # normalize Unicode/punctuation, exact aliases first,
        # then conservative single-token Levenshtein only for length >= 6
        ...
```

Implementation must scan tokens in order, accept `scorpion`, `skorpion`, `scorpian`, and return the remainder after the matched token. Fuzzy matching is capped at distance 2 and may not match tokens shorter than six characters.

- [ ] **Step 4: Verify matcher GREEN**

```bash
pytest -q tests/test_wake_matcher.py
```

Expected: all matcher tests pass.

- [ ] **Step 5: Write failing VoiceSession tests**

```python
from scorpion.voice_state import VoiceSession, VoiceState


def test_wake_only_opens_exact_twenty_second_window(fake_clock):
    session = VoiceSession(wait_seconds=20.0, clock=fake_clock)
    session.acknowledge_wake(has_trailing_command=False)
    session.mark_ack_finished()
    assert session.state is VoiceState.WAITING_COMMAND
    fake_clock.advance(19.99)
    assert session.tick() is VoiceState.WAITING_COMMAND
    fake_clock.advance(0.01)
    assert session.tick() is VoiceState.STANDBY


def test_first_speech_stops_wait_timer(fake_clock):
    session = VoiceSession(wait_seconds=20.0, clock=fake_clock)
    session.acknowledge_wake(False)
    session.mark_ack_finished()
    fake_clock.advance(10)
    session.first_speech_started()
    assert session.state is VoiceState.LISTENING
```

- [ ] **Step 6: Run voice-state tests and verify RED**

```bash
pytest -q tests/test_voice_state.py
```

Expected: import failure because `scorpion.voice_state` does not yet exist.

- [ ] **Step 7: Implement VoiceSession and Mk III config fields**

```python
class VoiceState(str, Enum):
    STANDBY = "STANDBY"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    WAITING_COMMAND = "WAITING_COMMAND"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
```

Add settings for `wake_wait_seconds`, `command_end_silence_ms`, `command_max_seconds`, `wake_whisper_model`, `command_whisper_model`, and defaults from the spec.

- [ ] **Step 8: Verify Task 1**

```bash
pytest -q tests/test_wake_matcher.py tests/test_voice_state.py tests/test_mk2_config_cloud_gate.py
```

Expected: all pass and CloudGate behavior is unchanged.

---

### Task 2: VAD capture, dual Whisper profiles, and silent standby listener

**Files:**
- Create: `src/scorpion/vad.py`
- Modify: `src/scorpion/local_audio.py`
- Replace: `src/scorpion/listener.py`
- Create: `tests/test_vad.py`
- Modify: `tests/test_local_audio.py`
- Modify: `tests/test_listener.py`

**Interfaces:**
- Produces: `VADSegmenter.feed(frame)`, `SpeechCaptureResult`, `LocalAudioService.transcribe_wake(path)`, `transcribe_command(path)`, `capture_until_silence(...)`.
- `VoiceListener` owns the microphone loop but emits state/command events; it never writes “wakeword missing” text to chat.

- [ ] **Step 1: Write failing VAD/listener tests**

```python
def test_non_wake_speech_is_silent(fake_listener):
    fake_listener.feed_transcript("heute ist schönes wetter")
    assert fake_listener.commands == []
    assert all("wakeword" not in message.lower() for message in fake_listener.user_messages)


def test_wake_only_speaks_exact_ack_and_waits(fake_listener):
    fake_listener.feed_transcript("Scorpion")
    assert fake_listener.spoken == ["Ja, Herr Rodriguez."]
    assert fake_listener.state == "WAITING_COMMAND"
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_vad.py tests/test_listener.py tests/test_local_audio.py
```

Expected: failures for missing VAD/dual-profile APIs and old fixed-chunk behavior.

- [ ] **Step 3: Implement VAD framing**

```python
class VADSegmenter:
    def __init__(self, sample_rate=16000, frame_ms=30, aggressiveness=2): ...
    def is_speech(self, pcm_frame: bytes) -> bool: ...
```

Use `webrtcvad` only on valid 16 kHz mono 16-bit frames. Track RMS microphone level separately for HUD telemetry.

- [ ] **Step 4: Refactor LocalAudioService for wake/command models**

```python
class LocalAudioService:
    def transcribe_wake(self, path: Path) -> str: ...
    def transcribe_command(self, path: Path) -> str: ...
    def capture_until_silence(self, *, onset_timeout, end_silence_ms, max_seconds) -> SpeechCaptureResult: ...
```

Maintain separate cached Whisper model instances keyed by model name. If command model `auto` is unresolved, controller/model manager supplies the selected concrete model.

- [ ] **Step 5: Replace listener with VoiceSession-driven flow**

```python
if wake_match and not wake_match.trailing_text:
    pause_capture()
    speak("Ja, Herr Rodriguez.")
    resume_capture()
    wait_for_first_speech(timeout=20.0)
elif wake_match and wake_match.trailing_text:
    pause_capture()
    speak("Ja, Herr Rodriguez.")
    on_command(wake_match.trailing_text, transcript)
```

No branch may emit a “heard X but not wakeword” UI/chat message.

- [ ] **Step 6: Verify Task 2**

```bash
pytest -q tests/test_vad.py tests/test_listener.py tests/test_local_audio.py tests/test_natural_tts.py
```

Expected: wake acknowledgement, 20-second first-speech behavior, end silence, hard cap, and TTS suppression all pass.

---

### Task 3: Adaptive store, hardware profiling, and local model manager

**Files:**
- Create: `src/scorpion/adaptive.py`
- Create: `src/scorpion/hardware.py`
- Create: `src/scorpion/model_manager.py`
- Create: `tests/test_adaptive.py`
- Create: `tests/test_hardware.py`
- Create: `tests/test_model_manager.py`

**Interfaces:**
- Produces: `AdaptiveStore`, `HardwareProfile`, `HardwareProfiler.profile()`, `ModelManager.recommend(profile, installed_models)`, benchmark recording APIs.
- Adaptive file defaults to `%USERPROFILE%/.scorpion/adaptive.json` and never stores raw audio/image bytes.

- [ ] **Step 1: Write failing deterministic hardware/model tests**

```python
def test_balanced_profile_from_mocked_resources():
    profile = classify_hardware(total_ram_gb=24, available_ram_gb=16, vram_gb=8, logical_cores=16)
    assert profile.capability == "balanced"


def test_prefers_installed_quality_equivalent_model():
    manager = ModelManager()
    pick = manager.recommend(profile="balanced", installed_models={"qwen3:8b", "gemma3:4b"})
    assert pick.text_model == "qwen3:8b"
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_hardware.py tests/test_model_manager.py tests/test_adaptive.py
```

Expected: missing modules.

- [ ] **Step 3: Implement safe hardware probes**

```python
@dataclass(frozen=True)
class HardwareProfile:
    capability: str
    total_ram_gb: float
    available_ram_gb: float
    vram_gb: float | None
    cpu_logical: int
    cpu_physical: int | None
    gpu_name: str | None
```

Use `psutil` plus fixed argument arrays for `nvidia-smi`; optional fixed CIM probe may use only a hard-coded query and never concatenate user input.

- [ ] **Step 4: Implement static model catalog and recommendation logic**

```python
MODEL_CATALOG = {
    "gemma3:4b": {"tier": "low", "vision": True},
    "qwen3:8b": {"tier": "balanced", "vision": False},
    "gemma3:12b": {"tier": "performance", "vision": True},
    "qwen3:14b": {"tier": "performance", "vision": False},
}
```

No method may run `ollama pull` without a `confirmed=True` argument supplied by the controller after a user dialog.

- [ ] **Step 5: Implement AdaptiveStore guardrails**

```python
ALLOWED_KEYS = {
    "accepted_wake_aliases", "wake_alias_success", "false_trigger_counts",
    "vad_aggressiveness", "mic_device", "wake_whisper_model",
    "command_whisper_model", "model_metrics", "text_model", "vision_model",
    "voice", "voice_rate", "voice_pitch", "ui",
}
```

Reject bytes and disallowed keys; require three separate-session observations plus explicit confirmation before activating a brand-new alias.

- [ ] **Step 6: Verify Task 3**

```bash
pytest -q tests/test_hardware.py tests/test_model_manager.py tests/test_adaptive.py
```

Expected: all pass.

---

### Task 4: Role-based local AI routing and stronger Scorpion persona

**Files:**
- Modify: `src/scorpion/local_ai.py`
- Modify: `src/scorpion/router.py`
- Modify: `src/scorpion/persona.py`
- Modify: `src/scorpion/app.py`
- Modify: `tests/test_local_ai.py`
- Modify: `tests/test_router.py`
- Modify: `tests/test_controller.py`

**Interfaces:**
- `OllamaLocalAI.respond(..., model=...)` accepts an explicit role-selected model.
- Controller exposes selected text/vision model and records latency/error metrics in `AdaptiveStore`.

- [ ] **Step 1: Write failing routing tests**

```python
def test_text_and_vision_use_different_selected_models(fake_ai, manager):
    controller = build_controller(text_model="qwen3:8b", vision_model="gemma3:12b")
    controller.handle("erklär mir quantenverschränkung")
    assert fake_ai.calls[-1].model == "qwen3:8b"
    controller.handle("was ist auf meinem bild?", image_bytes=b"jpeg")
    assert fake_ai.calls[-1].model == "gemma3:12b"
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_local_ai.py tests/test_router.py tests/test_controller.py
```

Expected: failures because Mk II.1 binds one model at construction.

- [ ] **Step 3: Add role-selected model parameter and metrics**

```python
def respond(self, user_text, history=(), image_bytes=None, *, model=None):
    selected_model = model or self.model
    payload = {"model": selected_model, "messages": messages, "stream": False}
```

Record duration and failures without storing prompt/image payloads in adaptive metrics.

- [ ] **Step 4: Upgrade persona without false claims**

Persona must instruct Scorpion to answer conversationally, mirror language, address the user naturally, remain concise by default, and be transparent about local model limitations. It must preserve CloudGate truthfulness and never claim ChatGPT equivalence.

- [ ] **Step 5: Verify Task 4 and CloudGate regression**

```bash
pytest -q tests/test_local_ai.py tests/test_router.py tests/test_controller.py tests/test_cloud_ai.py tests/test_cloud_guard_controller.py
```

Expected: all pass with no automated cloud spending.

---

### Task 5: Mk III command-center HUD and controller state events

**Files:**
- Create: `src/scorpion/hud.py`
- Modify: `src/scorpion/app.py`
- Create: `tests/test_hud_state.py`
- Modify: `tests/test_import.py`

**Interfaces:**
- Produces reusable `StatusCard`, `ConversationCard`, `CoreIndicator`, `SystemPanelModel` or equivalent pure state helpers testable without creating a real Windows display.
- Controller emits state snapshots containing voice state, countdown, mic level, text/vision model, Ollama status, hardware summary, voice status, and CloudGate status.

- [ ] **Step 1: Write failing pure HUD state tests**

```python
def test_waiting_state_shows_twenty_second_countdown():
    model = SystemPanelModel.from_voice_state("WAITING_COMMAND", remaining=20.0)
    assert model.voice_label == "WAITING 20s"
    assert model.countdown_visible is True


def test_openai_locked_is_default():
    assert SystemPanelModel().cloud_label == "OPENAI LOCKED 🔒"
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_hud_state.py tests/test_import.py
```

Expected: missing HUD module.

- [ ] **Step 3: Build new three-column HUD**

Use a 1280×720-safe grid:

```python
root.grid_columnconfigure(0, weight=0, minsize=170)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=0, minsize=270)
root.grid_rowconfigure(0, weight=1)
```

Left rail: Home/Chat, Vision, Systems, Memory, Updates, Settings. Center: conversation cards + core indicator + compact input bar. Right: state/model/hardware/voice/cloud status cards and countdown/mic level.

- [ ] **Step 4: Wire voice states and acknowledgement flow**

UI must display `STANDBY`, `ACKNOWLEDGED`, `WAITING 20s`, `LISTENING`, `THINKING`, `SPEAKING` without posting discarded standby speech into conversation history.

- [ ] **Step 5: Verify Task 5**

```bash
pytest -q tests/test_hud_state.py tests/test_import.py tests/test_controller.py tests/test_listener.py
```

Expected: all pass.

---

### Task 6: Signed GitHub Release updater, self-check, backup, and rollback

**Files:**
- Create: `src/scorpion/updater.py`
- Create: `src/scorpion/update_helper.py`
- Create: `src/scorpion/selfcheck.py`
- Create: `tests/test_updater.py`
- Create: `tests/test_update_helper.py`
- Modify: `src/scorpion/config.py`
- Modify: `src/scorpion/app.py`

**Interfaces:**
- `Updater.check()` fetches metadata only when repository config is present and respects 24-hour check throttling.
- `Updater.verify_manifest(manifest_bytes, signature_bytes)` uses a baked-in Ed25519 public key.
- `Updater.stage_update(...)` verifies signature + SHA-256 before exposing install action.
- `update_helper.apply(...)` backs up allowlisted core files, preserves user data, runs `python -m scorpion.selfcheck`, and restores backup on failure.

- [ ] **Step 1: Write failing verification and no-download-on-check tests**

```python
def test_check_does_not_download_payload(fake_github):
    updater = Updater(repo="owner/repo", transport=fake_github)
    updater.check()
    assert fake_github.asset_downloads == []


def test_invalid_signature_is_blocked(updater):
    with pytest.raises(UpdateVerificationError):
        updater.verify_manifest(b"{}", b"invalid")
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_updater.py tests/test_update_helper.py
```

Expected: missing updater modules.

- [ ] **Step 3: Implement metadata, signature, and hash verification**

```python
class UpdateVerificationError(RuntimeError): pass

ALLOWED_UPDATE_PREFIXES = (
    "src/scorpion/", "requirements.txt", "pyproject.toml",
    "run_scorpion.bat", "setup_scorpion.bat", "README.md",
)
```

Reject absolute paths, `..`, `.env`, user memory/adaptive paths, arbitrary scripts outside the allowlist, and manifests requiring a newer updater than supported.

- [ ] **Step 4: Implement helper backup/self-check/rollback**

```python
try:
    backup_current_core()
    replace_allowlisted_files()
    run_selfcheck()
except Exception:
    restore_backup()
    raise
```

Self-check imports core modules, parses settings, verifies CloudGate starts locked, and performs no cloud/network call.

- [ ] **Step 5: Wire Updates panel with explicit install confirmation**

Checking may occur automatically once per 24 hours. Payload download and installation begin only after the user presses `Installieren` and confirms the dialog.

- [ ] **Step 6: Verify Task 6**

```bash
pytest -q tests/test_updater.py tests/test_update_helper.py tests/test_cloud_ai.py tests/test_cloud_guard_controller.py
```

Expected: verification/rollback tests pass and cloud guard remains unchanged.

---

### Task 7: Setup, migration, dependencies, and first-run hardware/model recommendation

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `setup_scorpion.bat`
- Modify: `README.md`
- Modify: `tests/test_setup_script.py`
- Create: `tests/test_mk3_config.py`

**Interfaces:**
- Setup installs `webrtcvad-wheels`, `psutil`, `cryptography` while preserving the fail-fast behavior introduced in Mk II.
- Existing `SCORPION_LOCAL_MODEL` remains a manual override; missing value enables AUTO model selection.

- [ ] **Step 1: Write failing setup/config tests**

```python
def test_mk3_defaults_are_local_and_twenty_seconds(monkeypatch):
    monkeypatch.delenv("SCORPION_WAKE_WAIT_SECONDS", raising=False)
    settings = Settings.from_env()
    assert settings.wake_wait_seconds == 20.0
    assert settings.command_whisper_model == "auto"


def test_setup_installs_mk3_dependencies():
    text = Path("requirements.txt").read_text().lower()
    assert "webrtcvad" in text and "psutil" in text and "cryptography" in text
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_mk3_config.py tests/test_setup_script.py
```

Expected: missing Mk III settings/dependencies.

- [ ] **Step 3: Update configuration and setup docs**

`.env.example` must expose the Mk III knobs without including secrets. README must explain AUTO model selection, confirmation-gated downloads, GitHub update configuration, 20-second voice flow, and migration that preserves `.env`/memory/models.

- [ ] **Step 4: Verify Task 7**

```bash
pytest -q tests/test_mk3_config.py tests/test_setup_script.py tests/test_persona_config.py
```

Expected: all pass.

---

### Task 8: Full regression, release packaging, and secret/safety audit

**Files:**
- Modify as required by failing regression tests only.
- Create release archive outside repo: `/mnt/data/SCORPION_MkIII.zip`

**Interfaces:**
- Produces a clean Windows ZIP without `.env`, `.venv`, cache, Git metadata, raw audio, screenshots, or API secrets.

- [ ] **Step 1: Run complete test suite**

```bash
pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Compile all Python modules**

```bash
python -m compileall -q src/scorpion
```

Expected: exit code 0.

- [ ] **Step 3: Run safety/secret checks**

```bash
! grep -RInE 'sk-[A-Za-z0-9_-]{20,}' . --exclude-dir=.venv --exclude='*.md'
! find . -name '.env' -o -name '*.wav' -o -name '*.jpg' -o -name '*.png'
```

Expected: no real API keys and no runtime private media in release sources.

- [ ] **Step 4: Build release ZIP from allowlisted source files**

```bash
python - <<'PY'
from pathlib import Path
import zipfile
root = Path('.')
out = Path('/mnt/data/SCORPION_MkIII.zip')
exclude_parts = {'.git', '.venv', '__pycache__', '.pytest_cache'}
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob('*'):
        if not p.is_file() or any(part in exclude_parts for part in p.parts):
            continue
        if p.name == '.env' or p.suffix in {'.pyc', '.wav'}:
            continue
        z.write(p, Path('SCORPION_MkIII') / p.relative_to(root))
print(out)
PY
```

- [ ] **Step 5: Extract the ZIP into a fresh directory and rerun tests**

```bash
rm -rf /mnt/data/scorpion_mk3_release_check
mkdir -p /mnt/data/scorpion_mk3_release_check
unzip -q /mnt/data/SCORPION_MkIII.zip -d /mnt/data/scorpion_mk3_release_check
cd /mnt/data/scorpion_mk3_release_check/SCORPION_MkIII
pytest -q
```

Expected: zero failures from the packaged artifact.

- [ ] **Step 6: Final requirement audit**

Confirm line-by-line that the release satisfies: silent non-wake speech, exact acknowledgement, 20-second time-to-first-speech, VAD/end-silence hard cap, hardware auto-brain, role-based models, safe adaptive storage, polished HUD state model, confirmation-gated downloads/updates, signature/hash checks, rollback, and unchanged one-use OpenAI approval semantics.
