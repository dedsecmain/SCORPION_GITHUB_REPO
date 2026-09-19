# Scorpion MK47 v47.0.0

MK47 is the intelligence and comfort update following MK23.

## Highlights

- Adds a deterministic local Context Engine for domain, project, complexity, seriousness, language and routing priority.
- Defaults ordinary responses to High German and locally retries clear English drift once when German was expected.
- Adds relevance-ranked local long-term memory recall with bounded prompt injection.
- Connects context priority to local model routing for speed vs quality decisions.
- Adds a local Improvement Advisor that can propose fixes but never auto-apply them.
- Adds an INTELLIGENCE HUD status with context, memory recall, selected route and open ideas.
- Adds High German context hints to local command transcription.
- Normalizes known harmless read-only action aliases so they do not trigger unnecessary critical confirmations.
- Keeps unknown, mutating and critical actions fail-closed or confirmation-gated.
- Keeps direct OpenAI use approval-gated and preserves MK23 privacy/update protections.

## Deliberately not in MK47

MK50 remains the separate stability update for Ollama connection resilience, always-on wakeword behavior, boot autostart and related reliability work.

## Update path

A correctly installed MK23 recognizes `v47.0.0` as newer and can offer the signed MK47 release through the existing updater. Installation remains user-confirmed and must pass Ed25519 signature verification, SHA-256 checks, allowlisting and post-install self-check.

## Privacy

MK47 does not add automatic cloud upload of recalled memory, screenshots or microphone audio. Improvement proposals are local and never auto-applied. The private release-signing key is not included in GitHub or release assets.
