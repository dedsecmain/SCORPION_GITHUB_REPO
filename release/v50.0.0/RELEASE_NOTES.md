# Scorpion MK50 v50.0.0

MK50 is the stability and Build Mode repair release following MK47.

## Build Mode repair

- Replaces the previous incomplete Build Mode concept with a deterministic local workspace.
- Adds cube, sphere and panel primitives.
- Adds index-pinch selection/drag, two-hand scaling and thumb-middle rotation.
- Adds a full mouse fallback so Build Mode remains usable without camera tracking.
- Adds voice command support for “Scorpion, Build Mode”.
- Adds a dedicated Build Mode HUD/navigation entry.
- Stops gesture-camera resources cleanly when the workspace or Scorpion closes.
- Moves gesture tracking to the current MediaPipe Tasks Hand Landmarker API.
- Caches the official Hand Landmarker model locally under ~/.scorpion/models.

## Stability work

- Adds bounded Ollama retries with exponential backoff for transient connection failures.
- Keeps direct cloud escalation locked behind the existing user confirmation flow.
- Makes the wake listener recover after temporary microphone, VAD or Whisper failures.
- Enables the wake listener by default.
- Enables current-user Windows Startup autostart by default.
- Preconfigures the official GitHub update repository.

## Safety and privacy

- Webcam frames are processed in memory and are not intentionally persisted.
- Build Mode manipulates only its virtual workspace.
- Destructive OS/file actions remain outside Build Mode and confirmation-gated.
- No .env, local memory, adaptive state, credentials or private signing keys are included in the release packages.

## Compatibility

MK47 recognizes v50.0.0 as a newer semantic version. Installation remains explicitly user-confirmed and must pass Ed25519 signature verification, package/file SHA-256 verification, allowlisting and post-install self-check.
