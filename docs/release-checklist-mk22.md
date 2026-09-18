# Scorpion MK22 release checklist

A release is considered live only after every item below is verified against the final commit.

- [ ] Windows CI: dependency install, compile and full pytest suite pass.
- [ ] `python -m scorpion.selfcheck` passes on the release tree.
- [ ] HUD identifies Scorpion MK22 and local screen context can be stopped cleanly.
- [ ] Wakeword, 20-second command window and barge-in are covered by tests.
- [ ] Unknown apps require explicit first-use trust; mutating/critical actions require fresh confirmation.
- [ ] Audit log contains metadata only and redacts secret-shaped values.
- [ ] Google Drive sync uploads only explicitly approved structured memory payloads.
- [ ] OpenAI calls remain per-use approval gated and LOCAL mode blocks direct calls.
- [ ] Release manifest contains only allowlisted application files.
- [ ] `.env`, `.scorpion/`, memory, adaptive data, credentials and signing keys are excluded.
- [ ] Manifest version is exactly `v22.0.0`.
- [ ] Ed25519 signature verifies with `release/SCORPION_RELEASE_PUBLIC_KEY.txt`.
- [ ] Update ZIP package SHA-256 and every listed file SHA-256 verify.
- [ ] Rollback restores previous core files after a forced self-check failure.
- [ ] Published GitHub release contains `manifest.json`, `manifest.sig`, `SCORPION_update.zip`, and `SCORPION_MK22.zip`.
- [ ] A published-asset verification run succeeds after upload.
- [ ] Existing installed updater can validate the release signing key before claiming auto-update compatibility.
