# Scorpion Mk I Design

## Goal
Turn Scorpion v0.1 into a Windows-first personal desktop assistant that can stay ready for the wake phrase "Scorpion", converse with lower latency, inspect the webcam or desktop on demand, focus approved applications/windows, remember recent conversation context, and present a more useful HUD.

## Scope
Mk I is a controllable desktop assistant, not unrestricted computer-use automation. It intentionally does not execute arbitrary shell commands, type into arbitrary applications, click arbitrary coordinates, install software, read passwords, or perform destructive file operations.

## Architecture

### Core controller
`ScorpionController` remains the single orchestration point. It routes text or voice requests to safe local commands first and to the AI second. It owns conversation memory and exposes status suitable for the HUD.

### Voice
Two paths coexist:
1. **Always-ready wake listener:** a background listener records short microphone windows, transcribes only those windows, and dispatches text that contains the configured wake phrase. It can be enabled/disabled from the HUD. This makes "Scorpion, ..." usable without pressing the mic button.
2. **Realtime voice session:** an optional OpenAI Realtime client provides low-latency audio/text interaction when the installed OpenAI SDK supports it. The standard transcription/TTS path remains the fallback.

The wake listener is opt-in because continuous transcription can incur API usage. The HUD must make the listening state obvious.

### Vision
`CameraService` keeps snapshot support. `ScreenService` captures the desktop into JPEG bytes. Requests such as "what is on my screen?" route a current screenshot to the AI. No background screen recording occurs.

### Windows actions
Local actions use a strict allowlist. Mk I supports opening approved apps and focusing already-open approved windows. Unsupported targets are rejected. Closing/killing processes is not included because that can discard unsaved work.

### HUD
The Tk desktop UI adds status chips for AI, wake listener, camera/screen readiness, a visible always-listening toggle, quick actions for screen and camera, and a compact event/status area. UI operations stay thread-safe through `root.after`.

### Memory
Recent chat remains local JSON. Mk I adds a session summary/status count but does not store raw microphone audio, screenshots, or webcam frames.

## Configuration
Environment variables configure model names, voice, wake phrase, memory path, listener chunk size, and whether the continuous wake listener starts enabled. API keys stay in `.env` and are never bundled into distributable archives.

## Error handling
Hardware/API failures must be surfaced as short status messages instead of crashing the UI. Background listener failures stop that listener and update its state. Local command failures return a result string that the assistant can display truthfully.

## Testing
Unit tests cover command parsing, wake-phrase extraction from continuous transcripts, screen JPEG conversion, allowlisted window resolution, listener lifecycle with fake audio services, configuration defaults, memory behavior, and controller routing without network calls. A full `pytest` run and Python bytecode compilation gate the release archive.

## Release artifact
The output is `SCORPION_MkI.zip`, containing source, tests, setup/run batch files, `.env.example`, README, and no secret `.env`, caches, or Git metadata.
