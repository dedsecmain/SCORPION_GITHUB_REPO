# 🦂 SCORPION MK22

Scorpion MK22 is a Windows-first, local-first desktop assistant with High German voice, adaptive local model routing, structured long-term memory, trusted-app automation, local screen context and a signed rollback-capable update path.

## Voice core

Wakeword: **Scorpion**

Acknowledgement:

```text
Ja, Herr Rodriguez.
```

If the wake phrase already includes a command, Scorpion processes it immediately after the acknowledgement. If you only say `Scorpion`, the first-speech window stays open for up to **20 seconds**. Barge-in lets new user speech interrupt Scorpion's own answer and return to listening.

The default natural voice is `de-DE-KatjaNeural` with a slightly reduced speaking rate. Edge TTS does not use OpenAI credits. For fully offline speech output, set:

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

Ollama is used for local text and vision models. MK22 selects installed models according to task type and hardware profile. Small deterministic commands do not need an LLM. More complex reasoning may use a stronger installed text model, while screen/image tasks use an installed vision-capable model.

Model downloads never happen silently. Scorpion asks before running any `ollama pull`.

## Long-term memory

Structured long-term memory is local-first and stored separately from the rolling conversation history. It can hold project notes, preferences and other approved entries.

Google Drive sync is disabled by default. When enabled, only explicitly approved structured memory entries or project blocks are eligible for upload. Raw screenshots, audio, tokens, passwords, cookies, private keys and arbitrary filesystem paths are not Drive-sync payloads.

## Screen context

MK22 can observe local window metadata such as the active application and visible window titles. Pixel capture is ephemeral and only used when a local screen-analysis action needs it. Screen images are not retained by the background monitor and are not sent to cloud AI automatically.

## App trust and confirmations

Known low-risk actions can run only after the target application has been explicitly trusted. A new app needs first-use approval. Mutating and critical actions require a fresh confirmation before execution.

The local audit log stores only bounded metadata such as action type, target identifier, whether confirmation was required and the result. It does not store arbitrary command bodies or screenshots.

## ChatGPT and OpenAI

`ASK CHATGPT` prepares a handoff prompt and opens ChatGPT without spending Scorpion's OpenAI API credits.

Direct OpenAI API use remains optional. LOCAL mode blocks it. HYBRID/CLOUD still require a fresh one-time approval for each direct API request that may consume credits.

## Signed updates

The official update channel defaults to:

```text
dedsecmain/SCORPION_GITHUB_REPO
```

Scorpion checks release metadata without downloading the payload. Installation requires explicit confirmation and then enforces:

1. Ed25519 manifest signature verification
2. release-version consistency
3. update ZIP SHA-256 verification
4. per-file SHA-256 verification
5. strict update-path allowlisting
6. post-install self-check
7. automatic rollback on self-check failure

`.env`, local memory, adaptive data, credentials and model caches are not valid update targets.

## Optional Google Drive setup

Set:

```text
SCORPION_DRIVE_SYNC_ENABLED=true
SCORPION_DRIVE_FOLDER=ScorpionMemory
```

OAuth credentials stay under the local Scorpion credentials directory. The client requests Drive file-level scope and sync is still approval-gated per structured memory payload.

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```

Automated tests do not perform paid OpenAI calls, real Drive uploads or destructive desktop actions.
