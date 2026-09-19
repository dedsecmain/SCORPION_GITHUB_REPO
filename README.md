# SCORPION AI

Official update repository for **Scorpion MK50**, a Windows-first local-first AI assistant.

## Current release

`v50.0.0`

MK50 is the stability and Build Mode repair update after MK47. It keeps the MK47 context, memory and signed-update core while fixing the missing Build Mode implementation, strengthening Ollama resilience, keeping the wake listener alive through transient failures and enabling Windows autostart by default.

## MK50 highlights

- **Real Build Mode core** with deterministic object state for cube, sphere and panel objects.
- **Local hand gestures** through MediaPipe Tasks Hand Landmarker:
  - index pinch selects and drags
  - two-hand pinch scales
  - thumb + middle-finger motion rotates
  - release drops the selected object
- **Mouse fallback** for selection, drag, scale and rotation when camera or gesture tracking is unavailable.
- **Voice launch** with “Scorpion, Build Mode” plus a dedicated HUD button.
- **Ollama recovery** with bounded retries and exponential backoff for transient local connection failures.
- **Wake listener recovery** after temporary microphone/VAD/Whisper errors instead of silently dying.
- **Wakeword enabled by default** on application start.
- **Windows autostart** through the current-user Startup folder, no admin rights required.
- **Current MediaPipe 1.x Tasks API** and a locally cached official Hand Landmarker model.

## Privacy

Build Mode remains local-first:
- webcam frames are processed in memory and are not intentionally written to disk;
- the MediaPipe hand model is cached locally under `~/.scorpion/models/`;
- direct OpenAI use remains approval-gated per request;
- local memory, OAuth credentials, API keys and private signing keys are excluded from release packages.

## Update security

Scorpion checks GitHub Releases for newer versions. Installation still requires explicit confirmation and enforces:

1. Ed25519 manifest signature verification
2. release-version consistency
3. update ZIP SHA-256 verification
4. per-file SHA-256 verification
5. strict update-path allowlisting
6. post-install self-check with rollback on failure

The updater remains pinned to `dedsecmain/SCORPION_GITHUB_REPO`.

## Release assets

Each MK50 release contains:

```text
manifest.json
manifest.sig
SCORPION_update.zip
SCORPION_MK50.zip
```

The private Ed25519 release-signing key is never committed to this repository.

## Legacy bootstrap note

The historical `SCORPION_MkIII.zip` contains an older placeholder updater key. That historical build still needs the one-time trusted public-key migration before it can safely accept current signed releases.
