# Scorpion Mk II Local-First Design

## Goal

Turn Scorpion into a Windows-first assistant that can be useful without OpenAI API credits. Local execution is the default. ChatGPT handoff is the second route. Direct OpenAI API use is the last route and is forbidden unless the user explicitly approves that specific request.

## Product rules

1. **Local by default.** Starting Scorpion must not require an OpenAI API key and must not create OpenAI API traffic.
2. **No silent spending.** Every OpenAI API request requires an explicit, per-request approval immediately before the request. There is no “always allow” mode in Mk II.
3. **ChatGPT handoff is not an API call.** Scorpion may prepare a prompt, copy it to the clipboard, and open ChatGPT in the user’s browser. It must never scrape, automate, or treat the ChatGPT web app as an unofficial backend API.
4. **No paid wake loop.** Wake listening and speech transcription use local components only.
5. **Graceful degradation.** Missing Ollama, missing local models, missing local speech packages, or missing an API key must produce a clear status message rather than a crash.
6. **Safe PC control remains allowlisted.** No arbitrary shell, PowerShell, or coordinate-click automation is added by Mk II.

## Modes and routing

The HUD exposes three modes:

- **LOCAL**: only local services may run. OpenAI is locked.
- **HYBRID**: local services run first. When local handling is unavailable or the user chooses escalation, Scorpion offers ChatGPT handoff. Direct OpenAI remains locked behind per-request approval.
- **CLOUD**: direct OpenAI is available as an escalation path, but each request still requires explicit confirmation. Cloud mode never means blanket consent.

For ordinary chat, screen, or camera requests:

1. Try the local model when available.
2. If local inference is unavailable or fails, show the user three choices: retry locally, prepare for ChatGPT, or request OpenAI API use.
3. “Ask ChatGPT” copies a prepared prompt containing the task and a bounded amount of text conversation context, then opens `https://chatgpt.com/`. Images are not silently uploaded; for screen/camera requests Scorpion explains that the image must be attached manually in ChatGPT.
4. “Use OpenAI once” opens a confirmation dialog that names the action and warns that API credits may be consumed. Only an affirmative result produces an approval token scoped to the current request. The token is consumed by the first cloud call and cannot be reused.

## Local AI

Scorpion talks to a locally installed Ollama server through its localhost HTTP API. No Python Ollama SDK is required.

Configuration:

- `SCORPION_LOCAL_MODEL=gemma3:4b` by default for text + image support.
- `SCORPION_OLLAMA_URL=http://127.0.0.1:11434`.
- The local client calls `/api/chat` with `stream=false`.
- JPEG screen/camera bytes are base64-encoded into Ollama's message `images` field for vision requests.
- Conversation history is truncated to a bounded recent window before sending to the local model.

Scorpion does not automatically download multi-gigabyte models during app startup. A setup helper may offer/install Ollama and the configured model only as an explicit user action.

## Local speech

Mk II replaces the paid transcription loop with local speech services:

- Audio capture continues through `sounddevice`, but WAV writing uses Python's standard `wave` module so SciPy is no longer required.
- Local transcription uses `faster-whisper` on CPU with INT8 by default. `SCORPION_WHISPER_MODEL=base` is the default.
- The first local transcription can download the selected Whisper model from its model source. The UI must indicate that this is a one-time local model download, not OpenAI API credit usage.
- Local TTS uses the Windows SAPI voice through `pyttsx3` when available. If local TTS is unavailable, Scorpion still returns text and reports voice as unavailable.
- The continuous wake listener uses the local audio/transcription service only.

OpenAI Realtime Voice is not started from the ordinary voice button in Mk II. If retained as an optional cloud feature, starting it requires the same explicit one-time cloud approval dialog because it can consume API credits continuously while active.

## Cloud guard

The OpenAI client is isolated behind `CloudGate`.

`CloudGate.request_approval(reason)` is a UI-facing request, while `CloudGate.consume(token)` validates and consumes a one-use token. The OpenAI service refuses to send a request without a valid, unconsumed token.

This separation prevents a future UI bug from accidentally turning “Cloud mode” into spending permission.

The HUD always shows one of:

- `OPENAI LOCKED 🔒`
- `OPENAI APPROVAL PENDING`
- `OPENAI ACTIVE ⚡` only while an approved cloud operation is executing

No API call is made merely to test whether the API key works.

## ChatGPT handoff

`ChatGPTHandoff` builds a pasteable prompt containing:

- Scorpion’s identity in a compact system-style preface,
- the user’s current task,
- a bounded recent text history,
- a note when a screen/camera image must be attached manually.

It places the result on the Windows clipboard and opens ChatGPT in the default browser. No credentials, cookies, browser automation, DOM scraping, or unofficial endpoints are used.

The user can paste the answer back into Scorpion manually. Mk II may include a “PASTE CHATGPT ANSWER” button that imports clipboard text into local memory, but it must not claim the text came directly from ChatGPT unless the user performed the handoff.

## UI

The Mk II header shows:

- current mode: `LOCAL`, `HYBRID`, or `CLOUD`,
- local model state: `OLLAMA READY`, `MODEL MISSING`, or `OLLAMA OFFLINE`,
- speech state,
- `OPENAI LOCKED 🔒` by default.

The side rail adds:

- mode selector,
- `ASK CHATGPT`,
- `LOCAL VOICE`,
- `WAKE ON / OFF`,
- `SCREEN`, `CAM`, and memory controls.

Direct OpenAI escalation is presented only when needed or explicitly requested. Confirmation text must state that the action can consume API credits.

## Setup and installation

`setup_scorpion.bat` must:

1. Stop immediately if virtual-environment creation or dependency installation fails.
2. Never print a success message after a failed `pip` command.
3. Warn when the install path is excessively long and recommend `C:\Scorpion`.
4. Install the base Python dependencies without SciPy.
5. Explain that Ollama is a separate local runtime and show the user the command for pulling the configured model.
6. Create `.env` from `.env.example` only when `.env` does not already exist.
7. Treat `OPENAI_API_KEY` as optional.

The README documents Ollama installation separately. Scorpion must still launch when Ollama is not installed so the UI can explain what is missing.

## Components

- `local_ai.py`: Ollama health/model checks and local chat/vision.
- `local_audio.py`: WAV recording, faster-whisper transcription, and local TTS wrapper.
- `cloud_gate.py`: one-use approval token semantics.
- `cloud_ai.py`: OpenAI Responses API, requiring a valid CloudGate token.
- `handoff.py`: ChatGPT prompt preparation, clipboard, browser opening.
- `router.py`: local-first decision logic and escalation result types.
- `app.py`: controller + Mk II HUD + approval dialogs.
- Existing `actions.py`, `commands.py`, `camera.py`, `screen.py`, `memory.py`, and persona remain focused modules.

Legacy Mk I cloud audio/realtime code may remain as isolated optional code only if no default Mk II path can call it without approval.

## Error handling

Expected failures return user-readable statuses:

- Ollama offline: explain how to start/install Ollama.
- Model missing: show exact `ollama pull <model>` command.
- Local speech package/model unavailable: keep text chat working and explain local speech setup.
- ChatGPT handoff clipboard failure: still open ChatGPT and show the prompt in a selectable dialog/text area.
- OpenAI API key missing after approval: cancel the cloud request without network traffic and explain how to add a key.
- Cloud call fails: consume the approval token anyway. Retrying requires a new explicit approval.

## Testing

Unit tests must cover:

- default mode is LOCAL,
- local route does not instantiate or call OpenAI,
- local Ollama request formatting for text and images,
- one-use CloudGate tokens cannot be reused,
- cloud service refuses requests with no token,
- ChatGPT handoff includes the task and bounded history and marks images as manual attachments,
- local listener uses local transcription service,
- setup script exits on dependency failure and contains no unconditional success path,
- existing allowlisted Windows command behavior remains unchanged.

Integration tests may mock localhost/network boundaries. No automated test may spend OpenAI credits.

## Out of scope for Mk II

- Browser DOM automation of ChatGPT.
- Automatically reading ChatGPT responses from the web UI.
- Unattended cloud spending.
- Arbitrary shell execution.
- Fully autonomous mouse/keyboard control.
- Training a custom neural wake-word model.
- 3D holographic rendering.
