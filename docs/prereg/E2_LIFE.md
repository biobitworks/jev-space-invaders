# E2 — Conway Life: immutable atoms, changing multi-scale context

**Question.** Can exact lower-level atoms remain immutable while higher-order deterministic context changes across scales?

**Input:** `S01_LIFE_CONTEXT_EVAL_V1`
- 32×32 torus.
- Families:
  - still: block, beehive, loaf, boat, tub
  - oscillator: blinker, toad, beacon
  - glider
  - spaceship: lwss
  - collision: glider → block, and glider → glider
- One-cell perturbations: every cell of the pattern's bounding box expanded by 1.
- Masked observations: 5 seeded masks at each of 10% and 25% of live-cell-bbox cells.
- T = 64 (collisions: 96).

**Scales**
- CELL = grid bits.
- LOCAL_PATTERN = the 3×3 index at the perturbed site.
- PERSISTENT_OBJECT = the multiset of catalogue-classified 8-connected components.

**Output:** `S01_LIFE_CONTEXT_RESULTS_V1`. Per perturbation:
- the flipped source cell
- local pattern before and after
- t=0 object multiset before and after
- first divergence step at each scale
- outcome at T, one of:
  - `recovered`: grid equal to the unperturbed grid at T
  - `destroyed`: empty at T while the reference is not
  - `new_structure`: an object class at T is absent from the reference at T
  - `changed`: otherwise

**Hypotheses**

| ID | Hypothesis |
|---|---|
| H2a (invariant) | The SourceAtomFCO content id of every initial grid is unchanged after all context computation (100%). |
| H2b | Masked object-classification accuracy at 25% ≤ accuracy at 10% (a monotone degradation check). |
| H2c | Descriptive only (no test): outcome counts per family and first-divergence distributions per scale. |

This experiment is about deterministic rule dynamics; it makes no biological or "emergence" claim.
