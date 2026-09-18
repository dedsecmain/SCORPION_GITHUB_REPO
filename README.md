# SCORPION AI

Official update repository for **Scorpion MK22**, a Windows-first local-first AI assistant.

## Current release

`v22.0.0`

MK22 combines High German voice interaction, barge-in, structured local long-term memory, approval-gated Google Drive memory sync, trusted-app control, local screen context, local vision, hardware-aware model routing, metadata-only auditing and a signed rollback-capable updater.

## Update security

Scorpion checks GitHub Releases for update metadata. Update payloads are downloaded only after explicit installation confirmation and must pass:

1. Ed25519 manifest signature verification
2. release-version consistency checks
3. update-package SHA-256 verification
4. per-file SHA-256 verification
5. update-path allowlisting
6. post-install self-check with rollback on failure

The updater is pinned to `dedsecmain/SCORPION_GITHUB_REPO`.

## Privacy

- No `.env`, OAuth credentials, API keys, local memory, adaptive-learning data, screenshots, microphone recordings or private signing keys belong in release packages.
- Google Drive sync is limited to individually approved structured memory entries or project blocks.
- Background screen context stays local and does not retain screenshots by default.
- Direct OpenAI use remains opt-in per request.
- App first-use trust and action-risk confirmations remain enforced.

## Release assets

Each MK22 release contains:

```text
manifest.json
manifest.sig
SCORPION_update.zip
SCORPION_MK22.zip
```

The private Ed25519 release-signing key is never committed to this repository.

## Legacy bootstrap note

The historical `SCORPION_MkIII.zip` contains an older placeholder updater key. That build cannot safely accept MK22's current release key until a one-time trusted key migration is performed. Signature verification is not bypassed to work around this.
