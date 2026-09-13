# Scorpion Assistant v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop assistant named Scorpion with AI chat, push-to-talk voice, TTS, webcam vision, local memory, and safe local commands.

**Architecture:** A small Python package isolates personality, wake parsing, memory, commands, AI, audio, camera, and GUI. The GUI orchestrates these services without allowing arbitrary command execution.

**Tech Stack:** Python 3.11+, CustomTkinter, OpenAI Python SDK, python-dotenv, OpenCV, sounddevice, scipy, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-scorpion-assistant-design.md`

## Global Constraints
- Windows 10/11, Python 3.11+.
- Activation phrase is `Scorpion`.
- Voice input is push-to-talk in v0.1.
- Arbitrary shell commands are unsupported.
- `OPENAI_API_KEY` stays in `.env` and is never committed.

---

### Task 1: Core parsers and memory
**Files:** Create `src/scorpion/wake.py`, `src/scorpion/commands.py`, `src/scorpion/memory.py`; test in `tests/`.
- [ ] Write failing tests for wake extraction, command parsing, and memory persistence.
- [ ] Run tests and confirm failures are due to missing modules.
- [ ] Implement minimum code to pass.
- [ ] Run tests and confirm green.

### Task 2: Personality and configuration
**Files:** Create `src/scorpion/persona.py`, `src/scorpion/config.py`, `.env.example`.
- [ ] Write failing tests for stable personality markers and config defaults.
- [ ] Run tests and confirm red.
- [ ] Implement minimal prompt/config.
- [ ] Run tests and confirm green.

### Task 3: Hardware/API services
**Files:** Create `src/scorpion/ai.py`, `src/scorpion/audio.py`, `src/scorpion/camera.py`, `src/scorpion/actions.py`.
- [ ] Add pure tests for image data URL construction and safe action lookup.
- [ ] Run red.
- [ ] Implement services with lazy imports/hardware access.
- [ ] Run green.

### Task 4: Desktop UI and launch scripts
**Files:** Create `src/scorpion/app.py`, `src/scorpion/__main__.py`, `requirements.txt`, `setup_scorpion.bat`, `run_scorpion.bat`, `README.md`.
- [ ] Add import smoke test.
- [ ] Run red if entrypoint missing.
- [ ] Implement UI and launch scripts.
- [ ] Run full test suite and compile check.

### Task 5: Package and verification
- [ ] Run `pytest -q`.
- [ ] Run `python -m compileall src`.
- [ ] Verify no API key is present.
- [ ] Create ZIP for delivery.
