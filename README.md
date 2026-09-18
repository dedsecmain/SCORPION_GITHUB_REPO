# SCORPION AI

Official update repository for **Scorpion MK23**, a Windows-first local-first AI assistant.

## Current release

`v23.0.0`

MK23 is the focused personality update after MK22. It keeps the MK22 voice, memory, local vision, trusted-app controls and signed updater, while adding a situational response-style engine.

## MK23 personality core

Scorpion now selects one of three local response modes for each request:

- **SIGNATURE** for normal conversation: confident, relaxed, playful and occasionally cheeky without forced slang.
- **FOCUSED** for coding, GitHub, update and technical work: direct, precise and low on small talk.
- **SERIOUS** for health, emergencies, safety and other sensitive topics: calm, clear and no jokes.

The mode only changes response style. It does not weaken truthfulness, privacy, confirmation gates or cloud restrictions.

## Update security

Scorpion checks GitHub Releases for newer versions. Update payloads are downloaded only after installation confirmation and must pass:

1. Ed25519 manifest signature verification
2. release-version consistency checks
3. update-package SHA-256 verification
4. per-file SHA-256 verification
5. update-path allowlisting
6. post-install self-check with rollback on failure

The updater is pinned to `dedsecmain/SCORPION_GITHUB_REPO`.

## Privacy

- No `.env`, OAuth credentials, API keys, local memory, adaptive-learning data, screenshots, microphone recordings or private signing keys belong in release packages.
- Google Drive sync remains approval-gated for structured memory data.
- Background screen context remains local and does not retain screenshots by default.
- Direct OpenAI use remains opt-in per request.
- App first-use trust and action-risk confirmations remain enforced.

## Release assets

Each MK23 release contains:

```text
manifest.json
manifest.sig
SCORPION_update.zip
SCORPION_MK23.zip
```

The private Ed25519 release-signing key is never committed to this repository.

## Legacy bootstrap note

The historical `SCORPION_MkIII.zip` contains an older placeholder updater key. That historical build cannot safely accept releases signed with the current release key until a one-time trusted key migration is performed. Signature verification is not bypassed to work around this.
