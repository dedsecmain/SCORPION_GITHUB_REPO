# Scorpion Mk I Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Scorpion Mk I as an always-ready, vision-capable, safely controllable Windows desktop assistant.

**Architecture:** Extend the existing Python/customtkinter v0.1 with isolated services for continuous wake listening, desktop screenshot capture, safe window focus actions, and optional Realtime transport while preserving fallback chat/transcription/TTS. Keep all local computer actions allowlisted and route everything through `ScorpionController`.

**Tech Stack:** Python 3.11+, OpenAI Python SDK, customtkinter, OpenCV, Pillow, sounddevice/scipy, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-scorpion-mk1-design.md`

## Global Constraints

- Windows-first desktop app.
- No arbitrary shell commands or arbitrary coordinate clicking.
- No destructive file/process actions in Mk I.
- No raw microphone audio, screenshots, or camera frames persisted by Scorpion.
- API keys only via environment/.env, never in archives.

---

### Task 1: Mk I command and configuration surface
**Files:** modify `src/scorpion/config.py`, `src/scorpion/commands.py`; test `tests/test_commands.py`, `tests/test_persona_config.py`.
**Interfaces:** produce new command kinds for screen capture and window focus plus listener configuration fields.
- [ ] Write failing parser/config tests.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement minimal parser/config changes.
- [ ] Re-run focused tests until green.

### Task 2: Screen vision and safe window focus
**Files:** create `src/scorpion/screen.py`, modify `src/scorpion/actions.py`; test `tests/test_screen.py`, `tests/test_services.py`.
**Interfaces:** `ScreenService.capture_jpeg() -> bytes`; allowlisted window matching/focus helpers.
- [ ] Write failing service tests.
- [ ] Verify red.
- [ ] Implement services.
- [ ] Verify green.

### Task 3: Continuous wake listener
**Files:** create `src/scorpion/listener.py`, modify `src/scorpion/wake.py`; test `tests/test_listener.py`, `tests/test_wake.py`.
**Interfaces:** listener start/stop/state and callback with command text/transcript.
- [ ] Write failing wake/listener tests with fake audio.
- [ ] Verify red.
- [ ] Implement listener.
- [ ] Verify green.

### Task 4: Optional Realtime voice transport
**Files:** create `src/scorpion/realtime.py`; test `tests/test_realtime.py`.
**Interfaces:** feature detection/session configuration that imports realtime dependencies lazily and fails cleanly when unavailable.
- [ ] Write failing configuration/availability tests.
- [ ] Verify red.
- [ ] Implement minimal optional transport wrapper.
- [ ] Verify green.

### Task 5: Controller and HUD integration
**Files:** modify `src/scorpion/app.py`, `src/scorpion/persona.py`; test `tests/test_controller.py`, `tests/test_import.py`.
**Interfaces:** controller routes screen/focus commands and exposes wake listener lifecycle; UI provides listening toggle and screen/camera actions.
- [ ] Write failing controller tests with fakes.
- [ ] Verify red.
- [ ] Implement controller routing.
- [ ] Build HUD integration with no network on import.
- [ ] Verify tests.

### Task 6: Packaging and release verification
**Files:** modify `requirements.txt`, `.env.example`, `README.md`, batch files if needed.
- [ ] Update docs/config for Mk I.
- [ ] Run full `pytest -q`.
- [ ] Run `python -m compileall -q src tests`.
- [ ] Inspect archive contents for secrets/caches/Git metadata.
- [ ] Build `/mnt/data/SCORPION_MkI.zip`.
