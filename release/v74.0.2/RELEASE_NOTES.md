# Scorpion MK74.0.2 v74.0.2

MK74.0.2 is a focused Build Mode stability hotfix.

## Fixed

- Adds separate pinch engage/release thresholds to stop rapid grab/release chatter near the gesture boundary.
- Tolerates short camera tracking dropouts before releasing the selected object.
- Smooths workspace landmark positions with an exponential moving average.
- Stabilizes left/right hand ordering so MediaPipe hand-order swaps do not cause sudden transform jumps.
- Clamps per-frame rotation spikes caused by landmark tracking errors.
- Clamps two-hand scale spikes while preserving deliberate scaling.
- Coalesces stale consecutive drag events before applying them in the Build Mode UI.
- Preserves mouse drag, scale and rotate fallback.

## Regression coverage

The MK74.0.2 test suite explicitly covers pinch hysteresis, one-frame tracking loss, movement smoothing, rotation spike protection, scale spike protection and UI motion-event coalescing.

## Existing protections retained

MK74.0.1 self-check behavior remains intact, including preserved user Wakeword/autostart preferences. MK74 autonomy, proactive intelligence, local-first behavior, MK50 stability work and the signed update chain are unchanged.

## Security

The release remains protected by Ed25519 manifest signing, SHA-256 package/file verification, path allowlisting, explicit update confirmation and post-install self-check with rollback on genuine failures.
