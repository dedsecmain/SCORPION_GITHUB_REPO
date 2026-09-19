# SCORPION AI

Official update repository for **Scorpion MK74**, a Windows-first local-first AI assistant.

## Current release

`v74.0.0`

MK74 is the autonomy, personality and proactive-intelligence update after MK50. It keeps MK50 Build Mode, Ollama recovery, always-on wake and Windows autostart while adding a central permission model for what Scorpion may do locally versus what must wait for explicit approval.

## MK74 highlights

- **Local-first Autonomy Policy**: local read-only observation and local computation may run without extra approval.
- **Fresh approval for cloud**: direct OpenAI/API use remains blocked until the user approves that exact request.
- **Fresh approval for updates and persistent changes**: Scorpion may recommend them, never silently apply them.
- **Proactive Engine**: detects relevant next steps from context, memory gaps, repeated local failures and pending improvement ideas.
- **No auto-execution of suggestions**: proactive ideas carry `auto_execute=false`.
- **Personality continuity**: Scorpion keeps a more consistent identity while serious situations still override banter.
- **HUD intelligence refinement**: shows LOCAL-FIRST state and the current suggested next move.
- **NEXT MOVE view**: exposes the current suggestion and clearly states when approval is required.
- **MK47 intelligence retained**: context engine, High German consistency, relevant memory recall and adaptive local model routing.
- **MK50 stability retained**: Build Mode, gesture repair, Ollama resilience, wake recovery and Windows autostart.

## Privacy and control

Scorpion remains local-first. Recalled memory, screenshots, microphone audio and Build Mode camera frames are not automatically uploaded to cloud AI. Direct cloud use, update application and persistent changes remain permission-gated.

## Update security

Installation requires explicit confirmation and enforces Ed25519 signature verification, version consistency, package and per-file SHA-256 checks, update-path allowlisting and post-install self-check with rollback.

## Release assets

Each MK74 release contains:

```text
manifest.json
manifest.sig
SCORPION_update.zip
SCORPION_MK74.zip
```

The private Ed25519 release-signing key is never committed to this repository.

## Legacy bootstrap note

The historical `SCORPION_MkIII.zip` contains an older placeholder updater key and still needs the one-time trusted public-key migration before accepting current signed releases.
