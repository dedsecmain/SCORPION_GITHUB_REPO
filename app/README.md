# 🦂 SCORPION MK74.0.1

Scorpion MK74.0.1 fixes the update self-check rollback bug and builds on the signed MK50 stability core and adds a stricter autonomy model plus proactive intelligence.

## Hotfix

The release self-check now validates technical capability without requiring the user's persisted Wakeword or Windows-autostart switches to be enabled. User preferences may be disabled without causing rollback. Fresh-install defaults remain enabled.

## Autonomy Policy

MK74 separates actions into clear permission classes:

- local read-only observation: allowed locally
- local computation and reasoning: allowed locally
- cloud/API use: fresh explicit approval required
- persistent or mutating changes: fresh explicit approval required
- applying an update: fresh explicit approval required

Unknown or unsafe action classes remain blocked by default.

## Proactive Engine

Scorpion can now suggest a useful next move when context supports it. Examples include checking repeated local-AI failures, reviewing pending improvement ideas, filling a missing project-memory gap or showing a plan for a complex task.

Suggestions are advice only. They use `auto_execute=false` and do not become permission to spend credits, change files or install updates.

## Personality and HUD

MK74 keeps the Scorpion identity more consistent across casual and technical work. Serious and sensitive contexts still override playful behavior immediately.

The Intelligence card now shows context, memory/model state, **LOCAL-FIRST**, and the current proactive suggestion. **🧭 NEXT MOVE** displays the suggestion with its permission boundary.

## Existing MK50 capabilities

Build Mode, local MediaPipe hand tracking, mouse fallback, Ollama retry/recovery, always-on wake defaults and Windows login autostart remain included.

Wake acknowledgement remains:

```text
Ja, Herr Rodriguez.
```

## Safety and cloud rules

Direct OpenAI use remains one-request-only after approval. Scorpion may propose an update or improvement but cannot treat a proposal as permission to apply it. Critical and mutating desktop actions retain their existing confirmation requirements.

## Qwen-first local brain

Scorpion now prefers a Qwen-family Ollama model for text, planning, coding and local agent work when it is installed. On lower-memory systems, `qwen3.5:4b` is the preferred starting point; Gemma remains the primary lightweight vision route when available. Ruflo roles reuse the same local Ollama backend sequentially instead of loading one large model per agent.

## Voice and Build Mode reliability

The natural voice default uses `de-DE-SeraphinaMultilingualNeural` with gentler rate/pitch settings and pause-aware text cleanup. Build Mode keeps object selection across rotation gestures, tolerates brief tracking dropouts, smooths hand motion, tries multiple camera indices/backends and keeps mouse selection active for wheel-scaling and right-drag rotation.

## Ruflo coordination

Scorpion can optionally use a locally installed Ruflo CLI as a coordination layer. Ruflo does not replace Ollama, Scorpion's personality, Voice Core, Wakeword, HUD, permission model, or signed updater.

Supported commands include:

```text
Ruflo Status
Ruflo plane ein Update für die Wakeword-Erkennung
```

The first integration creates a hierarchical Ruflo swarm and registers three specialized roles:

- `scorpion-coder` using Ruflo's `coder` role
- `scorpion-tester` using Ruflo's `tester` role
- `scorpion-update` using Ruflo's `production-validator` role

Ruflo coordination is treated as a local mutation and therefore requires explicit approval before Scorpion creates coordination state. Applying code or an update remains outside Ruflo and still requires Scorpion's normal explicit approval and signed update path.

Scorpion does not automatically download Ruflo or run `npx ruflo@latest` on startup. A local `ruflo` command must be available, or `SCORPION_RUFLO_COMMAND` must be set deliberately.

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```
