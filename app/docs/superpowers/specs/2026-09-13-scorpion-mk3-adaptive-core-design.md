# Scorpion Mk III Adaptive Core Design

## Goal

Turn Scorpion Mk II.1 into a polished Windows-first personal assistant that hears the user more reliably, acknowledges the wake phrase immediately with “Ja, Herr Rodriguez.”, waits up to 20 seconds for the command, chooses an appropriate local AI model for the user’s hardware, learns safe local preferences over time, exposes a substantially more organized HUD, and can update itself through confirmed GitHub Releases without requiring full reinstallation.

## Product principles

1. **Local-first remains the default.** Wake detection, command transcription, local chat, adaptive tuning, and ordinary speech output do not require OpenAI API credits.
2. **No silent spending.** Direct OpenAI API calls remain impossible without the existing one-use approval flow immediately before the request.
3. **Wake acknowledgement is deterministic.** When Scorpion recognizes the wake phrase, it speaks exactly `Ja, Herr Rodriguez.` before handling the request.
4. **Twenty seconds means time-to-first-speech.** After a wake-only call, Scorpion waits up to 20 seconds for the user to begin speaking. Once speech begins, the 20-second timer stops and Scorpion records the command until end-of-speech.
5. **Silence is silent.** A missed wake phrase or background noise must not produce chat messages such as “I heard X but not my wakeword.”
6. **Self-improvement changes configuration, not arbitrary code.** Scorpion may tune approved local settings from observed usage, but it may not invent, rewrite, or execute arbitrary source code.
7. **Updates require confirmation.** Scorpion may check for updates automatically, but it may not download/install a core update or a large model without explicit user approval.
8. **Safe Windows control remains allowlisted.** Mk III does not add arbitrary shell, PowerShell, coordinate-click, or unattended browser automation.

## Voice state machine

Voice interaction becomes a state machine owned by `VoiceSession`, rather than a loop that records fixed chunks and prints every transcription.

States:

- `STANDBY`: local microphone listener is running, but only wake recognition can trigger UI or speech.
- `ACKNOWLEDGED`: wake phrase was recognized; Scorpion pauses microphone capture while speaking `Ja, Herr Rodriguez.` so its own voice is not re-transcribed.
- `WAITING_COMMAND`: a 20.0-second time-to-first-speech window is active.
- `LISTENING`: user speech has started; the countdown is no longer relevant and Scorpion records until end-of-speech.
- `THINKING`: captured command is being parsed/routed.
- `SPEAKING`: Scorpion is reading the answer aloud; microphone capture is suppressed.
- `ERROR`: a recoverable microphone/transcription failure is shown in the HUD, then the session returns to `STANDBY`.

### Wake-only flow

1. In `STANDBY`, local VAD detects speech before any transcription is attempted.
2. A short speech segment is transcribed locally.
3. Wake matcher normalizes text and accepts the canonical word `scorpion` plus configured known variants. Built-in German/English-friendly variants include `skorpion` and `scorpian`.
4. On a match with no meaningful trailing command, transition to `ACKNOWLEDGED`.
5. Speak exactly `Ja, Herr Rodriguez.` using the configured Natural Voice with offline fallback.
6. Transition to `WAITING_COMMAND` and start a 20.0-second timer.
7. If no user speech starts before the timer expires, return silently to `STANDBY`.
8. If user speech begins, transition immediately to `LISTENING`, stop the timer, and capture until at least 800 ms of ending silence or a 30-second hard utterance cap.
9. Transcribe the complete command with the higher-accuracy command transcription profile, then route it as normal.
10. After the spoken answer finishes, return to `STANDBY`.

### Wake + command in one utterance

For input such as `Scorpion, öffne den Rechner`:

1. Recognize the wake phrase and extract the non-empty trailing command.
2. Speak `Ja, Herr Rodriguez.` while microphone capture is paused.
3. Skip `WAITING_COMMAND` because the command is already present.
4. Transition to `THINKING`, handle the extracted command, speak the result, and return to `STANDBY`.

### False trigger behavior

- Speech that does not contain an accepted wake form is discarded from the UI.
- No “wakeword missing” response is spoken or written.
- Repeated false positive aliases can be down-weighted locally.
- Repeated candidate aliases are never permanently learned from raw inference alone. A new alias must reach the proposal threshold and be explicitly accepted by the user before becoming an active wake alias.

## Voice activity detection and transcription

Mk III separates **speech segmentation**, **wake transcription**, and **command transcription**.

- `webrtcvad-wheels` provides local speech/no-speech segmentation using 16 kHz mono PCM frames.
- `faster-whisper` remains the local transcription engine.
- Wake transcription uses the configured wake model, default `base`, optimized for short segments.
- Command transcription uses a hardware-selected model with `small` as the preferred mid-range default. Low-memory systems may use `base`; stronger systems may use `medium` when benchmarks remain within the configured latency budget.
- Audio recording continues to use `sounddevice` and Python’s standard `wave` module. SciPy remains unnecessary.
- Raw microphone audio is temporary and deleted/garbage-collected after transcription. Adaptive learning does not persist raw audio.

Configuration:

- `SCORPION_WAKE_WORD=Scorpion`
- `SCORPION_WAKE_WAIT_SECONDS=20`
- `SCORPION_COMMAND_END_SILENCE_MS=800`
- `SCORPION_COMMAND_MAX_SECONDS=30`
- `SCORPION_WAKE_WHISPER_MODEL=base`
- `SCORPION_COMMAND_WHISPER_MODEL=auto`

## Wake matcher

`WakeMatcher` performs deterministic local matching.

Processing:

1. Unicode normalize.
2. Lowercase.
3. Remove punctuation around tokens.
4. Compare exact canonical/accepted aliases first.
5. Permit a conservative edit-distance match only for a single token near the expected wake length. The default maximum edit distance is 2, and fuzzy matching is disabled for tokens shorter than 6 characters.
6. Return both the matched wake span and trailing text after it.

The matcher must never treat a distant ordinary word as a wake phrase merely because it is phonetically approximate.

## Hardware profiler

`HardwareProfiler` runs at first launch and can be rerun from Settings. It collects only local machine capability data:

- total and available RAM through `psutil`,
- logical/physical CPU core counts,
- NVIDIA GPU name and VRAM through fixed read-only `nvidia-smi` calls when available,
- Windows GPU name and reported adapter memory through a fixed read-only CIM query when NVIDIA tooling is unavailable.

No arbitrary user-provided shell text is executed. Hardware information remains local unless the user explicitly exports diagnostics.

The result is a `HardwareProfile` with `low`, `balanced`, or `performance` capability class plus measured RAM/VRAM values.

## Local model manager

`ModelManager` owns local model selection independently from the Ollama transport.

Mk III ships a small static model catalog that maps capability requirements to Ollama tags and intended roles. The initial catalog is:

- `gemma3:4b`: fallback/general + vision model for low-memory systems.
- `qwen3:8b`: preferred balanced text model when system memory allows it.
- `gemma3:12b`: preferred stronger multimodal model when memory/VRAM headroom is sufficient.
- `qwen3:14b`: preferred stronger text reasoning model on performance-class systems.

Selection rules:

1. Prefer an already-installed compatible model over downloading another model when the quality tier is similar.
2. Never download a model automatically.
3. If the recommended model is missing, show its exact Ollama tag and estimated download class and ask for approval before invoking `ollama pull`.
4. Keep `gemma3:4b` as the safe fallback recommendation if hardware information is incomplete.
5. Store the chosen primary text model and vision-capable model separately so one model does not have to solve every task.

### Runtime benchmarking

Scorpion records local, non-sensitive runtime metrics:

- first-token/complete-answer latency where available,
- total response duration,
- whether the model caused memory pressure or an Ollama out-of-memory/error,
- whether voice/vision remained responsive during inference.

After enough samples, Scorpion may **recommend** a different model, but it may not install or switch to a newly downloaded model without confirmation.

## Answer quality and routing

Mk III separates fast system commands from conversational reasoning:

1. Allowlisted Windows commands are parsed and executed directly without involving the LLM.
2. Ordinary chat uses the selected local text model with a stronger Scorpion persona/system prompt and bounded memory.
3. Screen/camera questions use the selected local vision model.
4. If local inference fails or quality is insufficient, the existing escalation choices remain:
   - retry locally,
   - ChatGPT handoff,
   - OpenAI API once with explicit credit warning and one-use approval.

Scorpion must not claim it is equivalent to ChatGPT. The UI can report which local model produced an answer so the user can understand quality/performance tradeoffs.

## Adaptive learning core

`AdaptiveStore` persists non-sensitive tuning data at `%USERPROFILE%\.scorpion\adaptive.json`.

Allowed adaptive data:

- accepted wake aliases and per-alias success counts,
- false-trigger counts,
- VAD aggressiveness/energy calibration values,
- preferred microphone device identifier,
- selected wake/command Whisper profiles,
- response-latency statistics by local model,
- chosen local text/vision model,
- preferred voice/rate/pitch,
- UI preferences such as collapsed panels.

Not stored by the adaptive core:

- raw microphone audio,
- screenshots/camera frames,
- passwords/tokens,
- arbitrary filesystem content.

### Learning rules

- Existing accepted aliases may gain/lose weights automatically based on successful sessions and obvious false triggers.
- A brand-new wake alias requires at least 3 candidate observations across separate sessions and then explicit user confirmation before activation.
- Hardware/model recommendations may adapt from benchmarks but downloads and model switches that require a download remain confirmation-gated.
- Adaptive tuning must be resettable from Settings with a `Reset Adaptive Learning` action.

## Natural voice behavior

Mk II.1 Natural Voice remains the preferred speaker.

- Default: `de-CH-LeniNeural` through `edge-tts`.
- Offline fallback: `pyttsx3` / Windows SAPI.
- Wake acknowledgement text is fixed to `Ja, Herr Rodriguez.`
- Listener capture is paused while Scorpion speaks to prevent self-triggering.
- If the online Natural Voice service is unavailable, acknowledgement and answers fall back locally rather than blocking the command flow.

## HUD redesign

The Mk III UI is split into focused visual regions instead of one header, one rail of equal buttons, and a raw textbox.

### Layout

**Left navigation rail**

- Home / Chat
- Vision
- Systems
- Memory
- Updates
- Settings

Only context-relevant actions are shown for the selected section.

**Center workspace**

- conversation cards for user and Scorpion instead of raw log text,
- compact input bar at the bottom,
- microphone/send controls,
- a central Scorpion Core indicator above or integrated with the conversation header.

**Right system panel**

- voice state: `STANDBY`, `ACKNOWLEDGED`, `WAITING 20s`, `LISTENING`, `THINKING`, `SPEAKING`,
- animated 20-second command ring while waiting,
- live microphone level while listening,
- local text model and vision model,
- Ollama state,
- RAM and GPU/VRAM summary,
- Natural Voice state,
- `OPENAI LOCKED 🔒` / approval state.

### Visual language

- graphite/near-black base,
- restrained dark-blue surfaces,
- cool cyan as active-system accent,
- orange only for warnings, update attention, or possible API spending,
- generous spacing and consistent card radii,
- no decorative RGB gradients or densely stacked equal-priority buttons.

The UI must remain usable at 1280×720 and scale cleanly upward.

## Update system

Mk III uses **GitHub Releases** as the official update transport.

Configuration:

- `SCORPION_UPDATE_REPO` contains the GitHub `owner/repository` identifier.
- If it is absent, the Updates panel shows `Update channel not configured` and performs no network request.
- `SCORPION_UPDATE_CHANNEL=stable` by default. `beta` is an optional explicit user setting.

### Release format

Each compatible GitHub Release contains:

- `scorpion-update.json`: signed manifest containing version, channel, minimum compatible updater version, asset filename, SHA-256 hash, changelog summary, and restart requirement,
- `scorpion-update.json.sig`: Ed25519 signature of the manifest,
- `SCORPION_Update_<version>.zip`: differential core package containing only application files that may be replaced.

The updater has a baked-in public verification key. A manifest with an invalid signature or an asset with the wrong SHA-256 is rejected before installation.

### Update flow

1. Scorpion may check GitHub Releases for metadata automatically at startup no more than once every 24 hours.
2. Checking does not install or download the update payload.
3. When an update exists, HUD shows version, summary, approximate size, and `Details`, `Installieren`, `Später`.
4. Only `Installieren` starts the payload download.
5. Before replacement, create a backup under `%USERPROFILE%\.scorpion\backups\<current-version>\`.
6. Preserve `.env`, memory, adaptive data, Ollama models, Whisper models, and user configuration.
7. Launch a small `update_helper` process, close the main app, replace allowed core files, and run `python -m scorpion.selfcheck`.
8. If self-check succeeds, restart Scorpion on the new version.
9. If replacement or self-check fails, restore the backup and restart the previous version.
10. Report update/rollback status in the Updates panel on next launch.

The update package cannot add arbitrary post-install shell commands. The helper replaces only allowlisted application paths described by the signed manifest.

## Update confirmation rules

- Automatic update checking: allowed.
- Automatic payload download: not allowed.
- Automatic installation: not allowed.
- Automatic local-model download: not allowed.
- Automatic rollback after a failed approved update: allowed because it restores the prior known-good state.

## Components

New modules:

- `voice_state.py`: voice session state machine and 20-second time-to-first-speech logic.
- `vad.py`: WebRTC VAD framing, speech onset/end detection, microphone-level telemetry.
- `wake_matcher.py`: wake normalization, aliases, conservative fuzzy matching, trailing command extraction.
- `hardware.py`: local hardware profile and fixed read-only GPU probes.
- `model_manager.py`: bundled model catalog, compatibility selection, installed-model preference, benchmark statistics.
- `adaptive.py`: safe persistent adaptive settings and counters.
- `updater.py`: GitHub Releases metadata, signature/hash verification, update staging.
- `update_helper.py`: backup, allowlisted file replacement, self-check, rollback, restart.
- `selfcheck.py`: fast post-update health checks that require no cloud access.
- `hud.py`: Mk III layout, reusable status cards, conversation cards, Core indicator, countdown visualization.

Modified modules:

- `app.py`: controller orchestration, UI wiring, state events, update approval dialogs.
- `listener.py`: replaced/reduced to use `VoiceSession`; no fixed-chunk user-facing miss messages.
- `local_audio.py`: separate wake and command transcription profiles; expose PCM/VAD-friendly capture helpers.
- `local_ai.py`: accepts selected text/vision model rather than one fixed model for all tasks.
- `router.py`: routes commands/text/vision using the selected local role model and existing escalation guardrails.
- `config.py`: Mk III voice-state, model-auto, adaptive, and update settings.
- `persona.py`: upgraded assistant identity and response quality instructions while preserving truthfulness and cloud rules.
- `requirements.txt`: add `webrtcvad-wheels`, `psutil`, and signature-verification dependency.

## Error handling

- Microphone unavailable: show `MIC OFFLINE`, keep typed chat usable, and offer microphone selection in Settings.
- Wake transcription unavailable: show local speech setup guidance; do not fall back to paid cloud transcription automatically.
- Command model unavailable: fall back to the installed wake transcription model and show a non-blocking quality notice.
- Ollama offline: keep system commands, voice wake, typed UI, ChatGPT handoff, and Settings usable.
- Recommended Ollama model missing: show recommendation and approval-gated download action.
- Natural Voice unavailable: use local SAPI fallback.
- GitHub unreachable: leave current version untouched and show last successful update-check time.
- Invalid release signature/hash: reject update and display `UPDATE BLOCKED · verification failed`.
- Failed post-update self-check: rollback automatically and report the failure after restart.

## Testing

Automated tests must cover at minimum:

- non-wake speech in standby produces no chat/status error message,
- canonical and accepted wake variants are recognized,
- unrelated fuzzy words are rejected,
- wake-only input speaks exactly `Ja, Herr Rodriguez.`,
- wait window is exactly 20 seconds to first speech,
- first speech stops the wait timer,
- command recording ends on configured silence and respects the hard cap,
- wake + command in one utterance skips the second wait,
- listener is suppressed while Scorpion TTS is active,
- hardware profile classification is deterministic for mocked RAM/VRAM inputs,
- model manager prefers suitable installed models,
- model/model-update downloads require confirmation,
- adaptive core never persists raw audio/image bytes,
- new wake aliases cannot become active without user confirmation,
- GitHub metadata check does not install or download payloads,
- invalid update signatures and hashes are rejected,
- approved update backs up and preserves user data,
- failed self-check triggers rollback,
- UI/controller state transitions are consistent,
- existing one-use OpenAI CloudGate behavior remains unchanged,
- no automated test can consume OpenAI credits.

## Migration from Mk II.1

Mk III installer/update migration preserves:

- `.env`,
- conversation memory,
- existing Natural Voice settings,
- OpenAI key if already present,
- Ollama model files managed by Ollama,
- downloaded Whisper model cache.

Existing `SCORPION_LOCAL_MODEL` remains a manual override. When set to a concrete model tag, automatic primary text-model selection is disabled until the user switches Model Selection back to `AUTO` in Settings.

## Out of scope for Mk III

- training a custom neural wakeword model,
- autonomous rewriting of Scorpion source code,
- updates installed without user confirmation,
- automatic browser control or scraping of ChatGPT,
- arbitrary shell/PowerShell execution,
- unrestricted mouse/keyboard automation,
- uploading adaptive telemetry to a server,
- 3D holographic rendering.
