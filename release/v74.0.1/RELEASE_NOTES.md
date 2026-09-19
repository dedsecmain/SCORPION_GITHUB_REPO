# Scorpion MK74.0.1 v74.0.1

MK74.0.1 is a focused hotfix for the update rollback bug seen during MK50/MK74 upgrade attempts.

## Fixed

- Release self-check no longer treats preserved user preferences for Wakeword or Windows autostart as release-health requirements.
- A user may intentionally keep either preference disabled without causing the updater to roll back an otherwise healthy release.
- Fresh installations still default Wakeword and Windows autostart to enabled.
- Adds a regression test that runs the release self-check with both preferences disabled.
- Keeps MK74 autonomy, proactive intelligence, personality, memory/HUD refinements, MK50 Build Mode, Ollama recovery and signed-update protections unchanged.

## Why this matters

Previous release self-checks compared runtime user preferences against fresh-install defaults. Because the updater preserves local configuration, an older installation with one of those switches disabled could make a valid update fail its post-install self-check and roll back.

MK74.0.1 separates these concerns correctly: defaults are tested as defaults, while post-install release health validates capability and integrity rather than personal configuration choices.

## Security

The hotfix keeps the existing Ed25519 release-signing chain, package/file SHA-256 checks, path allowlisting, confirmation-gated installation and rollback on genuine self-check failures.
