# 0-Vita-1 (VITA01) — Post-rehearsal prospective confirmatory preregistration

**Status:** POST_REHEARSAL_PROSPECTIVE_CONFIRMATORY_PREREGISTRATION. This is **not** a blind preregistration.
- An exploratory rehearsal of E0–E3 and the E4A freeze ran first, in the Claude sandbox. It is preserved unchanged in `vita01/EXPLORATORY_REHEARSAL_RECEIPT.json`.
- Every hypothesis from `docs/prereg/E0…E4A` is retained **verbatim**; this document does not edit them.
- The **new** hypotheses (H1e_v2, H2d, and the P-claims and type tests) are written after the rehearsal. They are labelled as successors throughout.

**Freeze.** This file, the type contract, the schemas, the kernels, the experiment code, the runner, `requirements.txt` and the type-error tests are sealed by `scripts/freeze_vita01.py`. Confirmatory execution may start only after that commit is verified on the remote. `scripts/run_experiment.py` refuses to run if any frozen file changed afterwards.

**Evidence level.** Every E0–E4 object is `SIMULATED`. None may become IN_VITRO, IN_VIVO, a biological validation, or a causal biological result.

## Primary claims (P1–P6)

| Claim | Test | Confirmatory decision rule |
|---|---|---|
| P1 persistence | breakpoint/MMR lineage; `VITA_STATE_V1.predecessor_id` | SUPPORTED if `verify_breakpoints.py` passes after every stage and every result breakpoint names its prereg parent |
| P2 deterministic reconstruction | E0–E3 output rows compared to the rehearsal digests (`REPLAY_LEVEL_4` = byte-identical) | SUPPORTED if E0, E1 and E2 reach REPLAY_LEVEL_4 on the playing machine. The E3 deterministic rows are reported separately. Any mismatch is reported as PARTIAL with the differing experiment named. |
| P3 history sensitivity | E2 H2d (below) | as H2d |
| P4 bounded projection | `S01_CONTEXT_PACKET_V1` schema, plus the leakage check in `tests/test_kernels.py` and `tests/test_type_errors.py` | SUPPORTED if the freeze test log shows these tests passing |
| P5 type safety | T1–T7 in `vita01/TYPE_ERROR_TEST_REGISTRY.json` | SUPPORTED if every T-test passes in the freeze test log; any failure makes P5 NOT_SUPPORTED |
| P6 downstream utility | E4B only | **NOT_TESTED** in this preregistration. Nothing here can promote it. |

## Experiments (sample sizes, seeds and endpoints are fixed by the frozen code)

| Exp | Retained hypotheses (unchanged) | New successor hypotheses | Sample / seeds |
|---|---|---|---|
| E0 | H0a–H0e | none | 5 spaces × 2,002 states; seeds 1000–1004 |
| E1 | G1, H1a–H1e. H1d threshold stays **90%**. H1e keeps its original metric: if both medians are 1, H1e is recorded as FAIL_TO_REJECT_H0 with the note NULL / METRIC_NOT_DISCRIMINATING. | **H1e_v2**: in the sparse regime (single-cell IC), median steps-to-final-MAP-size is larger for missing_row than for exact (Mann–Whitney one-sided, p < 0.05). *Note: the rehearsal produced this subset but it was not inspected for this question before writing.* | 256 rules × 4 ICs × 5 corruptions |
| E2 | H2a, H2b, H2c (descriptive, recorded as OBSERVED) | **H2d (P3)**: at t ∈ {8, 16, 32, 48, 64} with the current frame held fixed, the motion label from CORRECT_HISTORY has accuracy ≥ 0.95; NO_HISTORY gives UNKNOWN for 100% of labelled objects; SHUFFLED_HISTORY accuracy is strictly below CORRECT_HISTORY. Also reported: the number of cases with the same current atom id but a different context. | 11 scenes; seeded masks, perturbations, and history shuffles |
| E3 | H3a–H3c | none. States above the kernel cap are **ABSTAIN_SIZE_LIMIT** (not PASS, not FAIL, no SAFE/UNSAFE label) and are excluded from H3a by rule; the count is reported. | 9×9/10 (300 boards), 16×16/40 (100 boards), ≤ 60 per stratum |
| E4A | frozen snapshot input only | none | 96 snapshots (48 with bombs, 48 without), seeds 1–5, replay-verified at freeze |

**Failure / null criteria.**
- A frozen-input mismatch, a replay mismatch, or a schema failure makes the stage FAILED and stops the ladder.
- A hypothesis that misses its threshold is NOT_SUPPORTED. A non-significant test is FAIL_TO_REJECT_H0.
- The experiment's terminal state is SUPPORTED only if every non-descriptive claim is SUPPORTED; otherwise PARTIAL. If a gate fails, FAILED.

**Oracle identity (E3).**
- Package: python-sat 1.9.dev15, solver Minisat22.
- Encoding: clue constraints use a seqcounter cardinality encoding; the global mine count uses a totalizer.
- `oracle_identity()` hashes the oracle's and the kernel's source into the receipt.
- The oracle's inference and neighbourhood geometry are independent of the kernel's; both take the same revealed-clue input and board generator.

**Private System 0.** Anticube math, ΔG*, Golden-Corridor ranking and private commitments are not in this repository. Arms that need them are NOT_TESTED.

**E4B gate.** No JEV or other decider query happens under this document. E4B requires a successor prereg that freezes:
- provider and model identity
- the credit and cost boundary
- matched-ablation arms
- the noninferiority margin (from E4A)
