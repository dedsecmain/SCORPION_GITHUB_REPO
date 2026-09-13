# 🦂 SCORPION Mk III

Scorpion Mk III is a Windows-first, local-first desktop assistant with an adaptive Voice Core, hardware-aware local model selection, a redesigned command-center HUD, confirmation-gated cloud use, and a signed update path.

## What changed in Mk III

When the wake listener is enabled, Scorpion silently ignores ordinary background speech. When it hears **Scorpion** (including conservative variants such as `Skorpion` or `Scorpian`) it says exactly:

```text
Ja, Herr Rodriguez.
```

If the wake phrase already contains a command, Scorpion executes/processes it immediately after the acknowledgement. If you only say `Scorpion`, it opens a **20-second first-speech window**. When you begin speaking during that window, the countdown stops and Scorpion records until roughly 800 ms of end silence or a 30-second hard cap.

The HUD shows `STANDBY`, `ACKNOWLEDGED`, `WAITING`, `LISTENING`, `THINKING`, and `SPEAKING` states instead of posting discarded microphone fragments into chat.

## Install

Use a short path such as:

```text
C:\Scorpion
```

Run:

```text
setup_scorpion.bat
```

Then:

```text
run_scorpion.bat
```

The setup script is fail-fast. If Python package installation fails, it exits with an error and never prints a fake success message.

## Local AI and AUTO model selection

Install Ollama for Windows separately. Mk III leaves `SCORPION_LOCAL_MODEL` blank by default. Scorpion profiles RAM, CPU and NVIDIA VRAM when available, then recommends local text and vision models. Installed suitable models are preferred.

Useful starter models:

```powershell
ollama pull gemma3:4b
ollama pull qwen3:8b
```

Higher-capability PCs can use larger models such as `gemma3:12b` or `qwen3:14b`. **Scorpion never runs `ollama pull` without explicit confirmation.**

To force one model for both text and vision, set for example:

```text
SCORPION_LOCAL_MODEL=gemma3:4b
```

## Adaptive Learning

Adaptive settings are stored locally in `%USERPROFILE%\.scorpion\adaptive.json` by default. The store only accepts approved configuration fields such as wake aliases, VAD settings, model metrics and voice/UI preferences. It does not store raw microphone audio, camera frames or screenshots.

A brand-new wake alias needs repeated successful observations across at least three sessions and explicit confirmation before it can become active.

## Voice

Wake detection and transcription use local `faster-whisper` plus WebRTC VAD. The default wake profile is `tiny`; command transcription defaults to `auto` and is resolved to a concrete local model by Scorpion.

Natural spoken answers use `edge-tts` with `de-CH-LeniNeural` by default. This does **not** use OpenAI credits, but the spoken text is sent to Microsoft's speech service. If it fails, Scorpion falls back to Windows `pyttsx3`.

For fully offline speech output:

```text
SCORPION_NATURAL_VOICE_ENABLED=false
```

## ChatGPT handoff and OpenAI

`ASK CHATGPT` prepares a prompt, copies it to the clipboard and opens ChatGPT. It does not automate or scrape the ChatGPT web app.

Direct OpenAI API use is optional. Even in HYBRID or CLOUD mode, every direct request requires a fresh one-time confirmation that warns about possible API credit use. LOCAL mode blocks direct OpenAI requests before any approval dialog.

## Signed GitHub Release updates

The updater is disabled while this is blank:

```text
SCORPION_GITHUB_REPO=
```

Once an official repository is configured, Scorpion may check release metadata at most once per 24 hours. A check does **not** download the update payload. Download and installation require explicit confirmation.

Update packages must pass:

1. Ed25519 manifest signature verification
2. package SHA-256 verification
3. per-file SHA-256 verification
4. update-path allowlisting
5. post-update self-check

If the self-check fails, Scorpion restores the previous core files. `.env`, local memory, adaptive settings and model caches are never valid update targets.

## Migration from Mk II.1

You can replace the application files while keeping your existing `.env`. Your local memory, adaptive data, Ollama models and Whisper caches live outside the release core and do not need to be re-downloaded.

New Mk III settings are optional and get safe defaults. If you want AUTO model selection, remove the old `SCORPION_LOCAL_MODEL=gemma3:4b` line or leave it blank.

## Security boundaries

Mk III still does not add arbitrary CMD/PowerShell execution, unrestricted mouse/keyboard automation, browser DOM scraping, unattended cloud spending or silent model/update downloads.

## Developer checks

```powershell
python -m pytest -q
python -m compileall -q src/scorpion
```

Automated tests do not spend OpenAI credits.
