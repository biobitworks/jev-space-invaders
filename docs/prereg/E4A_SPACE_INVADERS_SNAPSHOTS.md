# E4A — Space Invaders frozen snapshot panel (input freeze only)

No JEV calls happen in this breakpoint. It freezes the inputs and the analysis plan before any paid call.

**Input:** `S01_SPACE_INVADERS_SNAPSHOT_EVAL_V1`
- Snapshots come from the scripted policy (R0), seeds 1–5, `ALE/SpaceInvaders-v5` (frameskip 4, sticky 0.25).
- Every 10th step where the ship is visible. Stratified: bombs visible vs none. Up to 96 total, seeded selection.
- Each snapshot stores:
  - seed, step, and the policy (so the frame is reproducible by replay)
  - frame SHA-256 and RAM SHA-256, re-verified by replay at freeze time
  - runtime identity and legal actions
  - the perception_v1 compact state

**Arms.** Same source snapshot for all arms; there is never a recommended action.

| Arm | Status |
|---|---|
| RAW | perception_v1 state |
| ANTICUBE | RAW + public operator-declared labels per atom (identity × safety) |
| PERMUTED | ANTICUBE labels drawn from a different matched snapshot (seeded derangement) |
| SIZE_MATCHED_SHAM | RAW + a noninformative field of the same byte length as the ANTICUBE block |
| S0_CONTEXT, S0_GOLDEN | NOT_TESTED (private S0 not in repo) |

**Primary endpoint** (per arm, per snapshot):

    TOTAL_MS = S0 compile + serialization + decider latency
    NET_TIME_SAVED_MS = RAW_TOTAL_MS − ARM_TOTAL_MS

Reported as p50, p95, paired median difference and bootstrap 95% CI (10,000 resamples, seed 7).

**Quality.** Unsafe-transition proxy = lives lost within 12 steps when the chosen action is repeated for 3 steps and then NOOP, replayed from the snapshot.

**Noninferiority.** An arm is noninferior if its unsafe rate ≤ RAW unsafe rate + 0.05.

**Credit ladder** (JEV): blocks of 12 → 24 → 48 → 96 snapshots. Each block must validate, seal and push before the next. A provider exhaustion stops paid calls and triggers a CreditExhaustionReceiptFCO.
