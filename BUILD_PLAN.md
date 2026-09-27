# Build plan

## Proposed track: pilot (human selection pending)

Use ALE/SpaceInvaders-v5 with RAM observations. Encode compact state from current RAM, temporal byte deltas, prior action, reward/score/lives, and prior JEV confidence.

JEV receives one Choice question over six legal actions. The baseline receives the same state and Choice contract through TypeSafe's System One adapter.

## Fixed-seed experiment

Seeds: 1, 2, 3, 4, 5.

Phase A: environment/random-policy smoke tests (do not count as JEV evidence).
Phase B: five JEV episodes, pushed individually.
Phase C: five baseline episodes using identical seeds/configuration, pushed individually.
Phase D: only after the frozen 5+5 comparison, tune confidence handling or state compression and add clearly labeled successor runs.

## Originality proposal

Confidence-aware temporal control: do not just send a frame snapshot. Send deterministic state deltas and make confidence operational. Track whether low-confidence decisions predict misses/deaths and whether a hold-last-action policy improves score without hiding model uncertainty.

## Sponsor proposal (not enabled until human approval)

Mitosis candidate: persist per-episode strategy/failure summaries in Cortex and retrieve them before the next episode so the cross-game strategy state is shared, cited, and inspectable while JEV still chooses each move.

Tenki candidate: run fixed-seed replay/tuning jobs in disposable sandboxes or CI. Use it only if it is genuinely part of the reproducible evaluation path.

## Demo

First 15 seconds: split-screen or overlay showing the same state sent to JEV and the LLM, live decision latency, action, confidence, and score. The thesis should be visible before explanation: typed decisions happen inside the game loop; a text model is late.
