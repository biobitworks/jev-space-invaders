# Vithia-Space — Build and Evaluation Plan (BP-0007 → BP-0016)

Repo: `biobitworks/jev-space-invaders` · parent breakpoint: `UFA-JEV-BP-0006` (main `03931bf`)
Written: Sun 2026-09-27 · Entries lock: **Mon 2026-09-28 23:59 PT** (2026-09-29T06:59Z)

Claim policy unchanged: MEASURED_ONLY. A breakpoint records what was executed and observed. A Merkle root proves inclusion and identity, not correctness or causality.

---

## 0. Current constraints

| Item | State | Consequence |
|---|---|---|
| TypeSafe JEV key | none | Only runs with `provider: "typesafe"` count toward Performance. Request one now with `needs_jev_access: true` in the entry. |
| OpenJev (`openjev/openjev`) | open weights, same `/v1/systemone` request/response shape | Dev and evaluation decider only. Its model card says it is **not affiliated with TypeSafe**, so UFA will treat its runs as non-JEV. Weights are CC BY-NC 4.0. Keep it to research use and label every run `provider: "openjev"`. |
| ROM | bundled in `ale-py 0.12.1` (verified: `ALE/SpaceInvaders-v5` resets and steps at seed 1) | The BP-0006 "ROM not present" blocker is closed by a successor runtime dataset. PettingZoo/multi-agent-ALE is not needed for pilot. |
| Games played | 0 JEV, 0 baseline | Harness and auto-push come before any research layer. |
| Entry | not submitted | Critical path. Missing: team name, pitch, in-person, sponsor "how". |

---

## 1. Architecture (the deterministic Vithia layer)

```
RGB frame (source of truth)
 → atom extraction (pixel colours: ship, aliens, bombs, own shot, shields)
 → Anticube tag per atom: identity {SELF, NONSELF, UNKNOWN} × safety {SAFE, NONSAFE, UNKNOWN}
     atoms code cannot settle → QUESTION
 → cellular-automaton danger field D[t+k, col], k = 1..K
 → Minesweeper layer: P(hidden bomb) per column from firing-capable aliens
 → path integral over move sequences, horizon H:
     S(path) = Σ D along path − λ·reward;  w = exp(−S/ħ)
     per-first-move summary: share of weight, min S, #safe paths
 → state JSON (named fields, no raw RAM) → ONE decider request
     questions: move (choice over 6 ALE actions) [+ optional danger noul, A/B tested]
 → action → env.step → FCO receipt → results.json → git push
```

The decider (JEV, OpenJev, or LLM) always makes the move choice. Code never sends a "recommended move", only evidence. That keeps the UFA rule intact ("other models can help, but they can't fly the ship").

**G\* and ΔG\*.** These follow HydraDG's definition: G* = U* − τ·H_norm.
- U* is the realized danger burden at the position the chosen move leads to, read from the source of truth one step later.
- H_norm is the normalized Shannon entropy of the decider's returned probability distribution.
- ΔG* is G* of the decider minus G* of a reference decider on the same state.

This is a dimensionless information-state diagnostic, not thermodynamics (same claim ceiling as HydraDG).

---

## 2. Breakpoint chain

Each breakpoint is one append-only JSON in `governance/breakpoints/`. Its atoms are FCOs: code commit, input dataset, config, outputs, and receipts. Its FCG edges are typed relationships (`DERIVED_FROM`, `EXECUTED_WITH`, `EVIDENCE_FOR`, `COMPARED_WITH`), never causal. Section 5 has the hashing.

The **exit gate** is the measured condition that "moves the project forward". A breakpoint that fails its gate is still committed, as FAIL, and a successor is opened. Nothing is overwritten.

| BP | Name | Produces (FCO atoms) | Exit gate (measured) | Slot |
|---|---|---|---|---|
| 0007 | ROM_BOUND_RUNTIME | successor `RuntimeSourceDataset` (ale-py/gymnasium wheel hashes, ROM md5 as reported by ale-py), env smoke receipt for seeds 1–5 | `reset(seed=s)` gives identical first 100 frame hashes on two runs; **first MMR computed** over BP-0001…0007 | Sun AM |
| 0008 | HARNESS_AUTOPUSH | `harness.py`, `record_run()`, `validate_results.py` extended | 5 scripted-policy games (`served_model: "scripted-policy"`, `provider: "none"`) each pushed individually; validator passes (p95 ≥ p50, calls ≤ steps, tokens from `usage`) | Sun AM |
| 0009 | VITHIA_PREPROCESSOR | parser, Anticube tagger, CA field, Minesweeper, path integral; frozen test frames | unit tests on ≥ 20 frozen frames with hand-checked atoms; state JSON size (tokens) recorded; per-step preprocessing p50/p95 recorded | Sun PM |
| 0010 | CA_RULIOLOGY_DATASET | 256-rule dodge dataset (§3), its own `DatasetFCO` + FMO root | regenerates byte-identically from seed list; FMO verify PASS | Sun PM |
| 0011 | CA_EVAL_OPENJEV | per-rule decisions: random, path-integral oracle, OpenJev (and later LLM, JEV) | pre-registered stats (§3.4) executed; results FCO committed whatever the outcome | Sun night |
| 0012 | SI_DEV_OPENJEV | Space Invaders runs with OpenJev as decider (non-JEV, labeled) | ≥ 5 games pushed; J0 (raw state) vs V0 (Vithia state) ablation on the same seeds | Mon AM |
| 0013 | SI_JEV_COUNTED | 5 JEV games, seeds 1–5, V0 state | each game pushed before the next starts; `served_model` taken from the response | Mon (depends on key) |
| 0014 | SI_BASELINE | 5 LLM games, same seeds and state, via System One adapter | same logging; cost from provider `usage` | Mon |
| 0015 | SPONSOR_LOAD_BEARING | Tenki fan-out and Mitosis Cortex receipts (§4) | removal test: harness fails closed without each sponsor path | Mon PM |
| 0016 | ENTRY_FINAL | README reproduce section, demo URL, final entry resubmission receipt | server returns `"ok": true` with empty `missing_for_judging` | Mon ≤ 23:00 PT |

**Cut order if time runs short:** BP-0011's LLM arm, then BP-0015 Mitosis, then BP-0012's ablation. BP-0008, 0013, 0014 and 0016 are never cut, because they are what judges score.

---

## 3. Cellular-automaton evaluation dataset (ruliology arm)

### 3.1 Why

Space Invaders bombs are one hazard process. A sweep over all 256 elementary CA rules gives 256 hazard processes whose predictability ranges from trivial (class I) to periodic (II), chaotic (III, e.g. rule 30), and complex (IV, e.g. rule 110). That tests where a decision model's confidence tracks real danger, which a single game cannot do.

256 rules reduce to 88 distinct rules under reflection and complement symmetry. The primary analysis uses the 88 so that equivalent rules are not counted as independent evidence. All 256 are reported as a secondary analysis.

### 3.2 The micro-environment ("CA dodge")

- Width W = 16 columns. Each tick, a 1-D CA row evolves under rule R, and live cells become bombs falling toward the ship row. The spacetime diagram scrolls down onto the ship.
- Ship moves LEFT / STAY / RIGHT. A tick is survived if the ship's column is empty when the hazard row arrives.
- Initial conditions: fixed seeds, 20 random rows per rule plus the single-cell start.
- Episode: T = 200 ticks, or until the first hit.
- The decider sees the same state schema as in Space Invaders: atoms, Anticube tags, CA-projected danger, path summaries. Only the hazard generator changes.

### 3.3 Deciders

| Arm | Decider | Role |
|---|---|---|
| R | uniform random | floor; H_norm = 1 by construction |
| P | argmin-action path-integral oracle (code) | reference only, **never a counted Space Invaders decider** |
| O | OpenJev (local) | primary model arm until the JEV key arrives |
| J | TypeSafe JEV | same subset as O, once keyed |
| L | LLM via System One adapter | subset only (cost) |

Budget: R and P on the full grid (256 × 21 × 200). O and J on 88 rules × 5 seeds × 100 ticks = 44,000 decisions. L on 88 × 1 × 50 = 4,400 decisions. Record wall-clock, latency and cost for each arm.

### 3.4 Pre-registered analysis

These are committed in BP-0010 **before** any model arm runs.

Per rule we record survival ticks, hit rate, decider H_norm, U*, G*, ΔG* (decider minus R, and decider minus P), and calibration: Brier score and ECE of p(chosen move is safe).

Rule descriptors, computed from the CA alone:
- Langton λ
- spatial entropy of the hazard field
- next-row predictability, as mutual information between row t−1 and row t
- Wolfram class: taken from a cited table where one exists. Any computed label is marked `CLASS_SOURCE=COMPUTED_PROXY`.

Hypotheses:
- **H1.** The survival gain of O over R is larger for class I/II rules than for class III.
- **H2.** Decider H_norm rises with hazard-field entropy (Spearman ρ > 0).
- **H3.** Class IV rules have the largest between-seed variance in ΔG*.
- **H4.** ΔG* separates rules where the decider is well calibrated (low ECE) from rules where it is not.

Tests:
- Kruskal–Wallis across classes
- Spearman correlations against the descriptors
- seed-bootstrap 95% CIs
- Benjamini–Hochberg FDR across rules for per-rule claims

A null result is reported as a null result.

"Which ΔG* emerges" means this: the rules, and the rule descriptors, for which ΔG* is reliably non-zero after FDR correction.

### 3.5 Link back to the game

The descriptors computed for the 256 rules are also computed on the observed Space Invaders bomb field for each wave. The nearest rule class, and its tuned (τ, H, ħ), then parameterizes the path integral for that wave. This is the bridge between the research arm and the counted runs, and what Mitosis Cortex stores (§4).

---

## 4. Sponsors (integrated last, smoke-tested first)

Both must be load-bearing: removing either breaks a documented step.

**Tenki: cross-machine determinism and fan-out.**
- *Smoke test (free credits):* `pip install tenki`, create one sandbox, run `pytest` plus one CA rule, return the output hash. **Gate:** the hash equals the local run's hash. That doubles as a reproducibility proof the judges can read.
- *Load-bearing job:* the BP-0011 grid and the Space Invaders seed sweeps fan out across sandboxes. Each sandbox's result is an FCO whose hash is a leaf in that breakpoint's Merkle tree. The sandbox image identity is part of the runtime dataset.
- *Removal test:* without `TENKI_API_KEY`, the sweep step exits non-zero and says so.

**Mitosis Labs: Cortex as the cited parameter memory.**
- *Smoke test:* `curl https://mitosislabs.ai/api/v1` (no credential). Then log in with `mi login` or MCP OAuth, do one `cortex_remember` / `cortex_ask` round trip, and record the returned `universal_id` as an FCO.
- *Load-bearing job:* each BP-0011 finding (rule class → tuned τ, H, ħ, with its ΔG* evidence) is written with `cortex_remember`. At each episode start and each new wave, the harness calls `cortex_ask` and takes parameters **only** from the cited result. Every episode's outcome is written back.
- The call happens per wave, never per frame, so it adds no decision latency.
- *Removal test:* no Cortex means no parameters, and the harness refuses to start a V0 run.

Neither sponsor sees TypeSafe keys, private prompts, or anything outside the competition surface.

---

## 5. Merkle and MMR mechanics

Reuse the existing FMO V1 rules (`evidence/source_freeze/FMO_CONSTRUCTION.md`):

- leaf = SHA256("FMO_LEAF_V1\0" ‖ path ‖ "\0" ‖ bytes ‖ "\0" ‖ sha256)
- node = SHA256("FMO_NODE_V1\0" ‖ left ‖ "\0" ‖ right)
- the last node is duplicated at odd levels

Each breakpoint's **breakpoint root** is a Merkle root over its FCO atoms: code commit tree hash, input dataset root, config, outputs, receipts.

Breakpoint roots are appended to a **Merkle Mountain Range**, the same pattern as `vithia-verifiable-long-horizon-agents/scripts/verify_golden_route.py`. BP-0007 computes the first MMR, retroactively covering BP-0001…0006.

`scripts/verify_breakpoints.py` recomputes every breakpoint root and the MMR from scratch, trusting no stored root.

FCG edges live in `FCG_EDGES.json`, typed and non-causal. Example chain:

```
RuntimeSourceDataset(BP-0007) ─EXECUTED_WITH→ Harness(BP-0008)
CADataset(BP-0010) ─EVIDENCE_FOR→ RuleClassFinding(BP-0011) ─STORED_AS→ CortexMemory
CortexMemory ─PARAMETERIZED→ EpisodeRun(BP-0013) ─COMPARED_WITH→ BaselineRun(BP-0014)
```

`SIGNATURE=NOT_SIGNED` unless signing is actually executed.

---

## 6. Open items for Byron

1. Entry fields: team name, pitch, in-person, sponsor "how". Submit today with `needs_jev_access: true`.
2. Hardware for OpenJev. The weights need ~80 GB GPU (FP8 serve). The MLX 4-bit build (~15 GB) runs on an Apple silicon Mac, and GGUF Q4_K_M (~16.5 GB) runs on a 24 GB card. Latency measured on local hardware is not JEV's latency.
3. Baseline provider and key: OpenAI, Anthropic, or Gemini.
4. Tenki and Mitosis accounts: sign up so the smoke tests can run.
5. Demo video: record Monday after BP-0013/0014, lead with the J vs L latency overlay.
