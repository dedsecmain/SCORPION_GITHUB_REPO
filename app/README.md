# 🦂 SCORPION MK47

Scorpion MK47 is the intelligence and comfort upgrade built on the signed MK23 desktop core.

## Context Engine

Every local request receives a compact situation profile before model routing:

- response language, defaulting to High German
- general, technical or sensitive domain
- recognized project such as Scorpion or Playbox
- speed or quality priority
- bounded complexity score
- serious-mode override when safety or sensitive context requires it

The profile changes how Scorpion works, not just how she sounds.

## High German consistency

Normal Scorpion answers default to **Hochdeutsch (de-DE)**. An explicit request for another language can override this. If a German request returns a clearly English local-model answer, MK47 records the mismatch locally and attempts one local retry with an explicit High German instruction.

## Relevant Memory Recall

Structured long-term memory remains local-first. MK47 can retrieve a small, relevance-ranked set of entries using:

- overlap with the current request
- title matches
- memory importance
- matching project context

Only the selected bounded context is passed to the local model. The full memory store is not dumped into every request.

## Smarter local model routing

The MK47 context priority feeds the existing hardware-aware model router:

- **speed** can prefer a lighter installed local text model
- **balanced** keeps the normal route
- **quality** can prefer a stronger installed local text model

Repeated model failures can still demote an unhealthy model. Direct cloud AI remains confirmation-gated.

## Improvement Advisor

Scorpion can record local proposals when repeated issues are detected, such as language drift or repeated Ollama failures. Proposals are visible from the **IMPROVEMENTS** HUD/navigation entry.

Improvement proposals are suggestions only. They are stored with `auto_apply=false`; MK47 does not silently install, patch or deploy its own updates.

## HUD and voice refinements

The HUD now includes an **INTELLIGENCE** status showing current context, recalled-memory count, selected model and number of open improvement ideas.

Local command transcription receives a High German vocabulary/context hint for Scorpion, GitHub, Ollama and update-related commands. Wakeword acknowledgement remains:

```text
Ja, Herr Rodriguez.
```

The first-speech window remains up to **20 seconds** in MK47. Wakeword-always-on and larger stability changes remain separate MK50 work.

## Safety normalization

Known read-only aliases such as status checks, screen inspection, file listing/read and update checks are normalized as low-risk actions. Unknown actions still fail closed. Mutating and critical actions still require confirmation.

## Signed updates

The official update channel remains:

```text
dedsecmain/SCORPION_GITHUB_REPO
```

MK23 recognizes `v47.0.0` as a newer semantic version. Installation still requires explicit confirmation and enforces Ed25519 signature verification, package/file hashes, path allowlisting, post-install self-check and rollback.

## Developer verification

From `app\`:

```powershell
python -m compileall -q src tests
python -m pytest -q
$env:PYTHONPATH = (Resolve-Path src)
python -m scorpion.selfcheck
```

Automated tests do not perform paid OpenAI calls, real Drive uploads or destructive desktop actions.
