# Scorpion Mk II Local-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Scorpion Mk I into a Windows-first local assistant that uses local AI and local speech by default, hands complex tasks to ChatGPT without API billing, and can only spend OpenAI API credits after explicit one-request approval.

**Architecture:** The controller routes ordinary chat and vision to an Ollama localhost client, and speech to a faster-whisper/Windows-SAPI local audio service. Direct OpenAI usage sits behind a one-use `CloudGate`; ChatGPT handoff only prepares/copies a prompt and opens the browser. The existing allowlisted PC-control modules stay isolated and unchanged.

**Tech Stack:** Python 3.11+, CustomTkinter, stdlib urllib/json/base64/wave, Ollama localhost HTTP API, faster-whisper, sounddevice, pyttsx3, OpenAI Python SDK (optional cloud only), pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-scorpion-mk2-local-first-design.md`

## Global Constraints

- Windows-first desktop app; the app must still launch when Ollama, faster-whisper, local TTS, or an OpenAI API key is missing.
- Default mode is `LOCAL`; startup must not create OpenAI API traffic.
- Every direct OpenAI request requires an explicit per-request approval token and consumes that token on the first attempt, including failed attempts.
- ChatGPT handoff may copy text and open `https://chatgpt.com/`, but may not scrape, automate, or read the ChatGPT web UI.
- Wake listening and ordinary microphone transcription are local only.
- No arbitrary shell, PowerShell, or coordinate-click automation.
- `SCORPION_LOCAL_MODEL=gemma3:4b`, `SCORPION_OLLAMA_URL=http://127.0.0.1:11434`, and `SCORPION_WHISPER_MODEL=base` are defaults.
- Automated tests must not perform paid OpenAI calls.

---

### Task 1: Mk II settings and one-use CloudGate

**Files:**
- Modify: `src/scorpion/config.py`
- Create: `src/scorpion/cloud_gate.py`
- Modify: `src/scorpion/__init__.py`
- Test: `tests/test_mk2_config_cloud_gate.py`

**Interfaces:**
- Produces: `Mode(str, Enum)` values `LOCAL`, `HYBRID`, `CLOUD`; `Settings.mode`, `Settings.local_model`, `Settings.ollama_url`, `Settings.whisper_model`.
- Produces: `ApprovalToken`; `CloudGate.request_approval(reason: str) -> ApprovalToken | None`; `CloudGate.consume(token: ApprovalToken) -> None`; `CloudApprovalError`.

- [ ] **Step 1: Write failing tests** for LOCAL defaults and one-use approval behavior.
- [ ] **Step 2: Run** `python -m pytest tests/test_mk2_config_cloud_gate.py -q` and verify collection/import fails because Mk II symbols do not exist.
- [ ] **Step 3: Implement** `Mode`, Mk II settings, and a CloudGate whose callback is the only source of approval and whose token IDs are stored once then removed on consume.
- [ ] **Step 4: Run** `python -m pytest tests/test_mk2_config_cloud_gate.py -q` and verify pass.
- [ ] **Step 5: Commit** `feat: add Mk II modes and cloud approval gate`.

### Task 2: Ollama local AI and guarded OpenAI client

**Files:**
- Create: `src/scorpion/local_ai.py`
- Create: `src/scorpion/cloud_ai.py`
- Test: `tests/test_local_ai.py`
- Test: `tests/test_cloud_ai.py`

**Interfaces:**
- Produces: `LocalAIStatus(state: str, detail: str)` where state is `ready`, `offline`, or `model_missing`.
- Produces: `OllamaLocalAI.status() -> LocalAIStatus`; `OllamaLocalAI.respond(user_text, history=(), image_bytes=None) -> str`.
- Produces: `CloudAI.respond(token, user_text, history=(), image_bytes=None) -> str`; this must call `CloudGate.consume(token)` before constructing/sending the OpenAI request.

- [ ] **Step 1: Write failing local-AI tests** using an injected HTTP transport to assert `/api/tags`, `/api/chat`, bounded history, system persona, and base64 image formatting.
- [ ] **Step 2: Run** `python -m pytest tests/test_local_ai.py -q` and verify failure because `local_ai` is missing.
- [ ] **Step 3: Implement** Ollama HTTP behavior with stdlib `urllib`, explicit offline/model-missing exceptions, `stream=false`, and no SDK dependency.
- [ ] **Step 4: Write failing cloud tests** proving no-token and reused-token calls are rejected before any injected client call.
- [ ] **Step 5: Implement** `CloudAI` with lazy OpenAI client creation and one-token-per-attempt semantics.
- [ ] **Step 6: Run** `python -m pytest tests/test_local_ai.py tests/test_cloud_ai.py -q` and verify pass.
- [ ] **Step 7: Commit** `feat: add local Ollama AI and guarded cloud AI`.

### Task 3: Local microphone, transcription, TTS, and wake listener

**Files:**
- Create: `src/scorpion/local_audio.py`
- Modify: `src/scorpion/listener.py`
- Modify: `requirements.txt`
- Test: `tests/test_local_audio.py`
- Modify: `tests/test_listener.py`

**Interfaces:**
- Produces: `LocalAudioService.record_wav(seconds, sample_rate=16000) -> Path`; `transcribe(path) -> str`; `speak(text) -> bool`; `speech_status() -> str`.
- `ContinuousWakeListener` keeps its existing public constructor and consumes only the injected local audio interface.

- [ ] **Step 1: Write failing WAV test** with injected recorder data and assert a standard-library WAV header is written without SciPy.
- [ ] **Step 2: Write failing lazy-transcription/TTS tests** proving optional packages are imported only when used and missing packages return clear errors/status instead of breaking app import.
- [ ] **Step 3: Run** `python -m pytest tests/test_local_audio.py tests/test_listener.py -q` and verify failures are caused by missing local audio implementation.
- [ ] **Step 4: Implement** WAV writing with `wave`, lazy faster-whisper CPU/INT8 model loading, and pyttsx3 local speech.
- [ ] **Step 5: Update dependencies** to remove SciPy/OpenAI realtime extras and add `faster-whisper` + `pyttsx3` while keeping optional `openai` for guarded cloud requests.
- [ ] **Step 6: Run** `python -m pytest tests/test_local_audio.py tests/test_listener.py -q` and verify pass.
- [ ] **Step 7: Commit** `feat: move speech and wake listening local`.

### Task 4: ChatGPT handoff and local-first router

**Files:**
- Create: `src/scorpion/handoff.py`
- Create: `src/scorpion/router.py`
- Test: `tests/test_handoff.py`
- Test: `tests/test_router.py`

**Interfaces:**
- Produces: `ChatGPTHandoff.build_prompt(task, history=(), image_attached=False) -> str`; `copy_and_open(prompt) -> HandoffResult`.
- Produces: `RouteStatus` values `ANSWER`, `ESCALATION_REQUIRED`; `RouteResult(status, text, image_requires_manual_attachment=False)`.
- Produces: `AssistantRouter.handle_local(text, history=(), image_bytes=None) -> RouteResult`; local failures must not instantiate or call `CloudAI`.

- [ ] **Step 1: Write failing handoff tests** for bounded history, task inclusion, image-manual-attachment note, clipboard failure fallback, and ChatGPT browser URL.
- [ ] **Step 2: Write failing router tests** proving LOCAL calls only local AI and returns escalation choices when Ollama is unavailable.
- [ ] **Step 3: Run** `python -m pytest tests/test_handoff.py tests/test_router.py -q` and verify failure.
- [ ] **Step 4: Implement** bounded handoff prompt and injectable clipboard/browser functions.
- [ ] **Step 5: Implement** local-first router with no direct cloud fallback.
- [ ] **Step 6: Run** `python -m pytest tests/test_handoff.py tests/test_router.py -q` and verify pass.
- [ ] **Step 7: Commit** `feat: add ChatGPT handoff and local-first routing`.

### Task 5: Mk II controller and HUD

**Files:**
- Modify: `src/scorpion/app.py`
- Modify: `src/scorpion/persona.py`
- Replace: `tests/test_controller.py`
- Test: `tests/test_cloud_guard_controller.py`

**Interfaces:**
- `ScorpionController.handle(text, image_bytes=None) -> str` routes allowlisted PC actions locally and chat/vision through the local router.
- `ScorpionController.request_cloud_once(reason, text, image_bytes=None) -> str` obtains one approval token from `CloudGate`, returns a cancellation message on denial, and calls `CloudAI` only on approval.
- `ScorpionController.prepare_chatgpt_handoff(text, image_bytes=None) -> HandoffResult` never calls OpenAI.

- [ ] **Step 1: Write failing controller tests** for screen-to-local-vision, no-cloud LOCAL path, denied approval causing zero cloud calls, approved one-time cloud call, and local wake/audio creation without API key.
- [ ] **Step 2: Run** controller tests and verify failure.
- [ ] **Step 3: Refactor controller** to construct LocalAI, LocalAudioService, CloudGate, CloudAI, ChatGPTHandoff, and AssistantRouter without performing network calls during construction.
- [ ] **Step 4: Replace Mk I UI cloud assumptions** with Mk II mode selector, Ollama/speech status, `OPENAI LOCKED 🔒`, `ASK CHATGPT`, `LOCAL VOICE`, `WAKE ON/OFF`, `SCREEN`, `CAM`, `CLEAR MEMORY`, and explicit per-request cloud dialog.
- [ ] **Step 5: Remove ordinary-path Realtime Voice controls** so no default voice action can spend API credits.
- [ ] **Step 6: Run** `python -m pytest tests/test_controller.py tests/test_cloud_guard_controller.py -q` and verify pass.
- [ ] **Step 7: Commit** `feat: wire Mk II local-first controller and HUD`.

### Task 6: Fail-fast Windows setup, docs, and release verification

**Files:**
- Modify: `setup_scorpion.bat`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_setup_script.py`

**Interfaces:**
- `setup_scorpion.bat` exits nonzero on venv/pip failure, warns about long paths, preserves an existing `.env`, and never requires `OPENAI_API_KEY`.

- [ ] **Step 1: Write failing setup-script text tests** checking `|| goto :error`/errorlevel fail-fast behavior, SciPy absence, optional API-key wording, and long-path guidance.
- [ ] **Step 2: Run** `python -m pytest tests/test_setup_script.py -q` and verify failure against Mk I script.
- [ ] **Step 3: Implement** fail-fast setup and update `.env.example` with LOCAL defaults and optional cloud settings.
- [ ] **Step 4: Rewrite README** with `C:\Scorpion` install path, Ollama install/start instructions, `ollama pull gemma3:4b`, one-time faster-whisper download explanation, three routing modes, ChatGPT handoff flow, and API-credit guard behavior.
- [ ] **Step 5: Run full suite** `python -m pytest -q` and verify zero failures.
- [ ] **Step 6: Run compile check** `python -m compileall -q src tests` and verify exit code 0.
- [ ] **Step 7: Run secret/release scan** ensuring no `.env`, `.git`, API keys, caches, or virtualenv files enter the archive.
- [ ] **Step 8: Commit** `release: prepare Scorpion Mk II local-first` and package `SCORPION_MkII.zip`.
