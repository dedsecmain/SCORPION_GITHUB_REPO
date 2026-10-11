# Scorpion MK74.0.3: Unified RED HOLO Core

This release unifies all prior MK22/MK23/MK47/MK50/MK74 fixes already in main with the previously unmerged Ruflo/Qwen and RED HOLO feature branch.

## Integrated functionality

- RED HOLO CORE: code-rendered red holographic scorpion, state-aware animation, dark red HUD and speaking attack motion
- Ruflo/Qwen local-first orchestration and fast/deep task workflows
- 3D Build Mode with perspective, camera controls, real mesh primitives and optional local mesh import
- MK74.0.2 Build Mode gesture protections retained: hysteresis, smoothing, tracking dropout grace, transform spike caps, stable hand ordering and event coalescing
- Hand-palm rotation is supported alongside the established gesture controls
- Better local German voice defaults and consistency
- Hologram imagery is included inside the signed update package
- Windows autostart uses version-independent Scorpion.cmd and safely migrates the old MK50 launcher if it is ours

## Security and privacy

- Signed updates only, using the existing Ed25519 public-key trust root
- Never include private signing keys, .env, credentials, audio, screenshots or user memory in packages
- Preserve local data and settings during updates
- Cloud AI, critical actions and update installation remain approval-gated
- The local 3D import must not execute scripts from imported assets

## Upgrade

MK74.0.2 users will see v74.0.3 as a newer official signed release once publication is complete. Update installation still requires explicit confirmation, signature verification, per-file hashes and post-install self-check with rollback.
