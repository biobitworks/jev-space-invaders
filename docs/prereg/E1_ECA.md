# E1 — ECA rule identification under partial/noisy observation

**Question.** Can the same evidence substrate identify compatible deterministic rule universes as partial or noisy observations arrive?

**Input:** `S01_ECA_256_EVAL_V1`

| Parameter | Value |
|---|---|
| Rules | all 256 |
| Width | 64, periodic boundary |
| Steps | T = 48 |
| Initial conditions | `single` (centre cell) and `rand1..rand3` (density 0.5, seeds 11, 12, 13) |

Corruptions of the **observation only** (the clean trajectory is the truth). Each is seeded by `hash(rule, ic, kind)`:

| Kind | Definition |
|---|---|
| exact | no corruption |
| missing_cell | 10% of cells unobserved |
| bit_flip | 2% of cells flipped |
| missing_row | every 4th row unobserved |
| mixed | 5% missing + 1% flipped + every 8th row unobserved |

The frozen input stores the clean trajectories and, for each corruption, its spec, seed and SHA-256 of the corrupted observation.

Independent cross-check: CellPyLib, rules {0, 30, 54, 90, 110, 150, 184, 255}, all 4 ICs, periodic boundary.

**Public reference S0.** Each observed consecutive pair (prev row, next row) yields (neighbourhood j → bit) evidence wherever all 4 cells are observed.
- `mismatch(rule)` = the number of evidence items the rule's table contradicts.
- `consistent` = rules with 0 mismatches.
- `MAP set` = rules with the minimum mismatch count.
- `true_rank` = 1 + the number of rules with strictly fewer mismatches than the true rule.
- `question` = the neighbourhood j that maximises the binary split entropy of the MAP set (its expected information gain in bits).
- `prediction` = majority vote of the MAP set on the next clean row, scored on cells whose clean neighbourhood is defined.

**Output:** `S01_ECA_256_RESULTS_V1`. Per (rule, ic, corruption): time series of |consistent|, |MAP|, true_rank, coverage (number of distinct j observed), prediction accuracy, question j and its EIG.

**Hypotheses**

| ID | Hypothesis |
|---|---|
| G1 (gate) | Our ECA output equals CellPyLib's on all cross-check cells. If this fails, E1 is FAILED. |
| H1a | Exact runs: the true rule is in the consistent set at every t in 100% of runs. |
| H1b | Exact runs: the final MAP set equals the observational equivalence class, i.e. the rules that agree with the truth on every observed j (100%). |
| H1c | Exact runs: median final log2 |MAP| is lower for random ICs than for the single-cell IC (Mann–Whitney one-sided, p < 0.05). |
| H1d | bit_flip, random ICs: final true_rank == 1 in ≥ 90% of runs. |
| H1e | Random ICs: median steps to reach the final MAP size is larger for missing_row than for exact (Mann–Whitney one-sided, p < 0.05). |

Golden-Corridor contraction and private context commitments: NOT_TESTED (private S0).
