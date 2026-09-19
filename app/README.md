# 🦂 SCORPION MK50

Scorpion MK50 is the stability and Build Mode repair release built on the signed MK47 core.

## Build Mode

MK50 replaces the earlier placeholder-style Build Mode with a real local workspace and state engine.

Supported local manipulations:
- index pinch: select and drag an object
- two-hand pinch: scale the selected object
- thumb + middle-finger motion: rotate the selected object
- release: drop the current selection
- mouse fallback: click/drag, mouse wheel scaling and right-drag rotation

The workspace currently supports cube, sphere and panel primitives. Gesture input only changes the local virtual workspace. File deletion, security changes and other destructive OS actions remain outside Build Mode and keep their normal confirmation gates.

Build Mode can be opened from the **🖐 BUILD MODE** button or by saying:

```text
Scorpion, Build Mode
```

## MediaPipe hand tracking

MK50 uses the current MediaPipe Tasks Hand Landmarker API. The official hand landmark model is cached locally under:

```text
~/.scorpion/models/hand_landmarker.task
```

Setup tries to preload it. If that download fails, Build Mode tries again on first gesture start and still retains the mouse fallback.

## Ollama resilience

Local Ollama calls use bounded retry with short exponential backoff for transient connection resets/timeouts. Retries stay local and never silently escalate to paid cloud AI.

## Always-on wake listener

The wake listener now defaults to enabled. A temporary microphone, VAD or Whisper failure puts the listener into a short **RECOVERING** state and then resumes listening instead of shutting itself down.

Wake acknowledgement remains:

```text
Ja, Herr Rodriguez.
```

The first-speech window remains **20 seconds** in MK50.

## Windows autostart

MK50 registers a current-user Startup launcher so Scorpion starts automatically at Windows login. It uses the local virtual environment and `pythonw.exe`, so no administrator permission is required.

Set this to disable it:

```text
SCORPION_AUTOSTART_ENABLED=false
```

## Safety and cloud rules

Direct OpenAI API usage still needs one-time approval for every request. Build Mode does not grant arbitrary shell, file-deletion or security-changing privileges. Mutating and critical desktop actions keep their existing confirmation requirements.

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```
