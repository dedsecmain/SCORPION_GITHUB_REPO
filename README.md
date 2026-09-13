# SCORPION AI

Official update repository for **Scorpion Mk III**, a Windows-first local AI assistant.

## Current release

`v3.0.0`

Scorpion checks GitHub Releases for update metadata. Update payloads are only downloaded after explicit user confirmation and must pass Ed25519 signature verification plus SHA-256 checks before installation.

## Security

- No `.env` files, API keys, local memory or adaptive-learning data are published here.
- Direct OpenAI use remains opt-in per request.
- Update installation always requires user confirmation.
- Failed self-checks roll back to the previous core.

## Release assets

Each Scorpion release contains `manifest.json`, `manifest.sig`, `SCORPION_update.zip`, and a full `SCORPION_MkIII.zip` package.

The private release-signing key is never committed to this repository.