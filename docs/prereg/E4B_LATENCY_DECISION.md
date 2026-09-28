# E4B_LATENCY_DECISION — preregistration (successor lane 1)

**Scope.** This lane measures runtime and decision behaviour on the frozen E4A panel (96 snapshots). It is **not** an action-quality experiment.

**E4A quality proxy** (12 decisions, action ×3 then NOOP): 67 of 96 snapshots lose a life under every action and 29 are safe under every action, so 0 are action-discriminating. This is recorded as **NULL / METRIC_NOT_DISCRIMINATING / NOT_A_PRIMARY_ENDPOINT**. It is a pre-execution design finding, not a model result, and E4A is unchanged.

**Decider.** OpenJev, `provider=openjev`, NON_TYPESAFE_JEV, NON_COUNTED. The runtime identity is frozen by `evidence/openjev/RUNTIME_MANIFEST.json` (must be `OPENJEV_LOADED=YES`) and `UPSTREAM_IDENTITY.json`.

**Arms.** A0_RAW, A1_VITACONTEXT (+3-decision history), A2_ANTICUBE (+ public operator labels), A4_PATH_DISTRIBUTION (+ public softmin path distribution, H=4, T=1; not ΔG*), A5_VITA01_FULL.

**Controls**
- NULL_METADATA: the same keys as A5, all null.
- SHUFFLED_HISTORY: the snapshot's own history in a seeded different order.
- SIZE_MATCHED_SHAM: a noninformative string the size of A5's extra bytes.
- UNRELATED_HISTORY: history from a seeded deranged other snapshot.

**A3_DELTAGSTAR** is NOT_TESTED / NOT_COMPUTED: no governed implementation is available, and none is substituted.

**Protocol.** The question and legal actions are the frozen `MOVE_QUESTION` over NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE. There is never a recommended action. One call is made per (snapshot, arm), in a seeded random order (seed 20260927), with no replicates. Probabilities are recorded as returned, else `NOT_AVAILABLE`. On request failure the harness holds the previous action; this is recorded as a fallback and counts against the valid-action rate.

**Primary endpoint.** Per arm vs A0 on the same snapshot: NET_TIME_SAVED = RAW_TOTAL − ARM_TOTAL, where TOTAL = S0 compile + serialization + decider latency.
- Test: two-sided Wilcoxon signed-rank, Holm-corrected across the 8 tested arms.
- SUPPORTED if Holm p < 0.05 and the median saving is > 0. NEGATIVE if Holm p < 0.05 and the median is ≤ 0. Otherwise FAIL_TO_REJECT_H0.

**Secondary (descriptive).** Valid-action rate, fallback rate, action-change rate vs A0, normalized entropy, request bytes. Action change is **not** evidence that either action is better.

**Stop conditions.** Stop if OpenJev fails to load, a frozen atom changes, or the endpoint is unreachable for the whole run. Budget: 864 local calls, zero cost.
