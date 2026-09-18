# Scorpion MK23 v23.0.0

MK23 is the deliberately smaller personality update following MK22.

## Highlights

- New local response-style engine with SIGNATURE, FOCUSED and SERIOUS modes.
- Everyday Scorpion is more confident, relaxed, playful and characterful without forcing slang.
- Technical and project work automatically shifts to a more precise, low-small-talk style.
- Health, emergency, safety and other sensitive requests automatically disable banter and switch to a calm serious style.
- The current user request is now passed into persona construction, so the local model receives the correct situational tone instructions.
- Desktop labels, self-check, updater identity and release metadata are updated to MK23 / v23.0.0.
- MK22's local-first privacy rules, cloud approval gates, trusted-app controls, signed updater and rollback protections remain intact.

## Update path

A correctly installed MK22 recognizes `v23.0.0` as newer. It checks the official GitHub release metadata and can offer the signed MK23 update through the existing updater flow.

Installation remains confirmation-gated. The update package must pass Ed25519 signature verification, package SHA-256 verification, per-file hash verification, path allowlisting and post-install self-check.

## Privacy

MK23 does not add automatic cloud uploads, screenshot retention, microphone recording retention or secret collection. The private release-signing key is not included in GitHub or release packages.
