# E3 — Minesweeper: incomplete knowledge over a fully determined hidden world

**Question.** Can the same substrate represent incomplete knowledge over a deterministic hidden world?

**Control.** After board generation, ontic randomness = none. The uncertainty is epistemic: which consistent world is true.

**Input:** `S01_MINESWEEPER_EVAL_V1`
- **Boards.** 9×9/10 with seeds 0..299, and 16×16/40 with seeds 0..99. The first click is (4,4) or (8,8), a guaranteed-safe opening.
- **State pool.** States are sampled along an **oracle-driven** play loop: reveal every SAT-forced safe cell; when none is forced, reveal a uniformly random *truly safe* cell (seeded). The pre-click state is included.
- **Strata, labelled by the SAT oracle only:**

| Stratum | Definition |
|---|---|
| determined | every hidden cell forced |
| partially_determined | some forced |
| ambiguous | none forced, frontier constraints exist |
| guess_required | none forced, no frontier constraints |

- **Sample.** Up to 60 states per stratum per board size, seeded.

**Kernel:** exact frontier enumeration + global mine count (component cap 28 variables; above the cap → BUDGET_EXCEEDED, reported).

**Questions**
- `max_eig`: the UNKNOWN cell with the highest expected information gain. Outcome distribution is {mine, clue 0..8}. Candidates are the 12 UNKNOWN cells with the lowest mine probability.
- `random`: a seeded random UNKNOWN cell from the same candidates.
- Actual gain: log2 W_before − log2 W_after(true outcome).

**Output:** `S01_MINESWEEPER_RESULTS_V1`

**Hypotheses**

| ID | Hypothesis |
|---|---|
| H3a | Kernel labels == SAT-oracle labels on 100% of cells in states with kernel status OK. |
| H3b | Actual gain(max_eig) > actual gain(random), paired one-sided Wilcoxon, p < 0.05, over states with ≥ 2 candidates. |
| H3c | Calibration: \|mean(actual gain) − mean(EIG)\| ≤ 0.10 bits for the max_eig question. |
