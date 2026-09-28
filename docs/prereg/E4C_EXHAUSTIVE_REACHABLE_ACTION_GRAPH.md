# E4C_EXHAUSTIVE_REACHABLE_ACTION_GRAPH — construction protocol

This supersedes the hold×4 → NOOP draft. That draft was never frozen or pushed; it is kept in git history only.

**Schema.** ALE six actions: NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE. The ECA-native LEFT/STAY/RIGHT schema is never used here.

| Parameter | Frozen value |
|---|---|
| Roots | scripted policy, seeds 6–15 (disjoint from E4A), every 10th decision with the ship visible; seeded sample of ≤ 240 (`E4C_EXHAUSTIVE_REACHABLE_ACTION_GRAPH\|roots`) |
| Expansion | restore the exact root; for each first action, expand all 6 actions per decision to H = 4 decisions (16 frames) |
| Node identity | SHA-256 of `ALEState.serialize()` (RAM, RNG and frame counters) at each depth; exact transpositions merge with path multiplicity |
| Terminal | life lost or game over; the branch stops |
| Compression | none (no deterministic interval is proven equivalent) |
| Per first action | survivable (any surviving leaf), safe paths, safe fraction = safe / 6^(H−1), nodes, merges |
| Derived | optimal-action set (max safe fraction among survivable), decision margin (best − second), regret per action |
| Discriminating | 1 ≤ number of survivable first actions ≤ 5 |
| Panel | discriminating roots, ≤ 48 per stratum (bombs / none), seeded |
| Gate | ≥ 24 discriminating, else **BLOCKED_OR_UNDERPOWERED** (the panel is recorded, not executed) |

**Execution endpoint (future prereg, after the panel gate).** Per arm vs A0:
- optimal-set hit rate, tested with McNemar exact and Holm correction;
- mean regret, tested with a paired Wilcoxon;
- minimum usable N = 24.

**Claim ceiling.** Exhaustive local safety to 16 frames; this does not measure game-score performance.
