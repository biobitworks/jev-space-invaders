# E0 — Addressability (Library-of-Babel design precedent)

**Question.** Can finite canonical states be reversibly addressed independently from their cryptographic content identity?

**Input:** `S01_ADDRESSABILITY_EVAL_V1`
- 5 spaces (k, n): (2,8), (2,64), (3,32), (26,20), (256,16)
- 2,000 seeded states per space (`random.Random(1000 + space_index)`)
- plus the all-min and all-max states

**Output:** `S01_ADDRESSABILITY_RESULTS_V1`

**Hypotheses (all must hold for SUPPORTED):**

| ID | Hypothesis | Threshold |
|---|---|---|
| H0a | `unrank(rank(s)) == s` and `parse(address_str)` round-trips | 100% of rows |
| H0b | address collisions among distinct states | 0 |
| H0c | content-id collisions among distinct states | 0 |
| H0d | address string equals content-id string, or address integer equals content-id integer | 0 rows |
| H0e | output rows file byte-identical to the reference-runtime digest | reports REPLAY_LEVEL_4 if equal, REPLAY_LEVEL_2 otherwise; does not change the terminal state |
