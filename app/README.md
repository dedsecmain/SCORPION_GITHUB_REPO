# 🦂 SCORPION MK23

Scorpion MK23 is a focused personality and response-style upgrade on top of the MK22 local-first desktop core.

## MK23 personality core

Each local text request is classified into a response style before it reaches the local model:

- **SIGNATURE**: confident, relaxed, playful, slightly cheeky, with light street flavor and no forced slang.
- **FOCUSED**: precise, direct and low on small talk for coding, GitHub, updates, debugging and project work.
- **SERIOUS**: calm and respectful with no jokes for health, emergencies, safety and sensitive situations.

Safety, truthfulness, privacy and confirmation rules always outrank personality styling.

## Voice core

Wakeword: **Scorpion**

Acknowledgement:

```text
Ja, Herr Rodriguez.
```

If the wake phrase already includes a command, Scorpion processes it immediately after the acknowledgement. If you only say `Scorpion`, the first-speech window stays open for up to **20 seconds**. Barge-in lets new user speech interrupt Scorpion's own answer and return to listening.

The default natural voice remains `de-DE-KatjaNeural` with a slightly reduced speaking rate. Edge TTS does not use OpenAI credits. For fully offline speech output, set:

```text
SCORPION_NATURAL_VOICE_ENABLED=false
```

## Install

Use a short Windows path such as:

```text
C:\Scorpion
```

Run:

```text
setup_scorpion.bat
run_scorpion.bat
```

## Local AI

Ollama is used for local text and vision models. MK23 keeps hardware-aware routing from MK22. Small deterministic commands do not need an LLM. More complex reasoning may use a stronger installed text model, while screen/image tasks use an installed vision-capable model.

Model downloads never happen silently. Scorpion asks before running any `ollama pull`.

## Long-term memory and Drive

Structured long-term memory remains local-first and separate from rolling conversation history. Google Drive sync is disabled by default and only explicitly approved structured memory entries or project blocks are eligible for upload. Raw screenshots, audio, tokens, passwords, cookies, private keys and arbitrary filesystem paths are not Drive-sync payloads.

## Screen context and app trust

Scorpion can observe local window metadata such as the active application and visible window titles. Pixel capture is ephemeral and used only when local screen analysis needs it. Screen images are not retained by the background monitor and are not sent to cloud AI automatically.

Known low-risk app actions require explicit trust. New apps need first-use approval. Mutating and critical actions require a fresh confirmation.

## ChatGPT and OpenAI

`ASK CHATGPT` prepares a handoff prompt and opens ChatGPT without spending Scorpion's OpenAI API credits.

Direct OpenAI API use remains optional. LOCAL mode blocks it. HYBRID/CLOUD still require a fresh one-time approval for each direct API request that may consume credits.

## Signed updates

The official update channel defaults to:

```text
dedsecmain/SCORPION_GITHUB_REPO
```

MK22 and newer installations compare semantic versions, so `v23.0.0` is recognized as an update. Installation still requires explicit confirmation and then enforces:

1. Ed25519 manifest signature verification
2. release-version consistency
3. update ZIP SHA-256 verification
4. per-file SHA-256 verification
5. strict update-path allowlisting
6. post-install self-check
7. automatic rollback on self-check failure

`.env`, local memory, adaptive data, credentials and model caches are not valid update targets.

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```

Automated tests do not perform paid OpenAI calls, real Drive uploads or destructive desktop actions.
