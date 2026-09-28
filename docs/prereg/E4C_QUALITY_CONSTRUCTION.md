# E4C_QUALITY — panel construction protocol (successor lane 2)

**Purpose.** Build a successor panel on which an action-quality endpoint *can* discriminate between actions, without modifying E4A. This protocol is frozen before the panel is built, and the panel is frozen before any model sees it.

**Mechanistic rationale.** In E4A, the doomed states lose a life on the first decision whatever the action. The ship is already hit, and ALE decrements lives only after the death animation. A state is therefore "committed" if a life is lost under NOOP within a short pre-screen. The pre-screen of 12 decisions (48 frames) is the E4A proxy horizon, the window in which every doomed E4A state resolved. The observed commit-lag distribution is recorded in `construction_summary.jsonl`.

| Parameter | Frozen value |
|---|---|
| Source states | scripted policy, `ALE/SpaceInvaders-v5`, seeds 6–15 (disjoint from E4A seeds 1–5), every 5th decision with the ship visible |
| Pre-screen | exclude if a life is lost (or game over) within 12 NOOP decisions |
| Action hold | candidate action held 4 decisions (16 frames) |
| Rollout after hold | NOOP (deterministic) |
| Evaluation horizon | unsafe = life lost or game over within 24 decisions of the snapshot |
| State restore | `ale.cloneState(include_rng=True)` / `restoreState` (tested: rollouts reproduce exactly) |
| Legal actions | NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE |
| Discriminating | 1 ≤ number of unsafe actions ≤ 5 |
| Duplicates | identical frame SHA-256: keep the first |
| Strata | bombs visible / none |
| Sampling | all discriminating states; if a stratum has more than 48, seeded sample of 48 (`E4C_QUALITY\|<stratum>`) |
| Gate | ≥ 24 discriminating snapshots in the panel, else **BLOCKED_OR_UNDERPOWERED** (the panel is recorded; no execution) |

**Endpoint (for the later execution prereg).** Unsafe rate of the chosen action, per arm (same arms as E4B), on the panel.
- Test: McNemar exact vs A0, Holm-corrected.
- Minimum usable N: 24 pairs without fallback.

**Claim ceiling.** Scripted-policy states with a NOOP rollout: this is a local-safety proxy, not game-score performance. The thresholds are not tuned on model outcomes; no model has seen these states.
