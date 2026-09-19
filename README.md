# SCORPION AI

Official update repository for **Scorpion MK47**, a Windows-first local-first AI assistant.

## Current release

`v47.0.0`

MK47 is the intelligence and comfort update after MK23. It keeps the signed local-first core while making Scorpion more context-aware, more consistent in High German, better at recalling relevant local memory and clearer about how it routes work.

## MK47 intelligence core

- **Context Engine** detects domain, project, complexity, seriousness and response priority for each request.
- **High German consistency** defaults normal answers to `de-DE` and locally retries clear English drift once when German was expected.
- **Relevant Memory Recall** ranks local long-term memories by query overlap, importance and project context instead of dumping the full memory store into prompts.
- **Context-aware Model Routing** can prioritize speed for casual work and stronger local models for technical or sensitive tasks.
- **Improvement Advisor** stores local improvement proposals from repeated issues, but never applies or installs them automatically.
- **Safety Normalizer** maps known read-only aliases to low-risk actions while unknown, mutating and critical actions still fail closed or require confirmation.
- **HUD Intelligence Status** shows the detected context, recalled-memory count, selected local model and pending improvement ideas.
- **Voice refinement** adds a High German command prompt to local Whisper transcription without sending microphone audio to cloud AI.

## Update security

Scorpion checks GitHub Releases for newer versions. Update payloads are downloaded only after installation confirmation and must pass:

1. Ed25519 manifest signature verification
2. release-version consistency checks
3. update-package SHA-256 verification
4. per-file SHA-256 verification
5. update-path allowlisting
6. post-install self-check with rollback on failure

The updater is pinned to `dedsecmain/SCORPION_GITHUB_REPO`.

## Privacy and control

- Relevant long-term memory is selected locally and is not automatically uploaded.
- Improvement proposals are stored locally and have `auto_apply=false`.
- No `.env`, OAuth credentials, API keys, local memory, adaptive-learning data, screenshots, microphone recordings or private signing keys belong in release packages.
- Direct OpenAI API use remains opt-in per request.
- App first-use trust and mutating/critical action confirmations remain enforced.

## Release assets

Each MK47 release contains:

```text
manifest.json
manifest.sig
SCORPION_update.zip
SCORPION_MK47.zip
```

The private Ed25519 release-signing key is never committed to this repository.

## Legacy bootstrap note

The historical `SCORPION_MkIII.zip` contains an older placeholder updater key. That historical build cannot safely accept releases signed with the current release key until a one-time trusted key migration is performed. Signature verification is not bypassed to work around this.
