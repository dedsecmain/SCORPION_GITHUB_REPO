# 🦂 SCORPION MK74

Scorpion MK74 builds on the signed MK50 stability core and adds a stricter autonomy model plus proactive intelligence.

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

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```
