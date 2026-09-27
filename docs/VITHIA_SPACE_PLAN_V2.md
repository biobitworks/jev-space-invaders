# Vithia-Space — Build Plan v2 (breakpoints BP-0009 → BP-0020)

Supersedes `VITHIA_SPACE_PLAN.md` (v1). v1 is kept as history; nothing in it is deleted.
Written: Sun 2026-09-27 · Entries lock: **Mon 2026-09-28 23:59 PT** (2026-09-29T06:59Z)
Official repo: `https://github.com/biobitworks/jev-space-invaders`, default branch `main`.

States used throughout: PROPOSED ≠ IMPLEMENTED ≠ EXECUTED ≠ OBSERVED ≠ SUPPORTED.

---

## 0. Recovered state (checked against the public remote)

| Item | State | Evidence |
|---|---|---|
| Remote `main` | `3095964e6a4fd898f52647f62a625c07e7c44165` | `git ls-remote` |
| Latest breakpoint on `main` | BP-0008 (sponsor source promotion) | `governance/breakpoints/` |
| Harness patch `019716f` | **NOT on remote**. Applies cleanly to `3095964`; 7 tests pass in the Claude sandbox. | local only → `REMOTE_IMPLEMENTATION_STATE=NOT_CONFIRMED` |
| PR #1 `intake/automata-minesweeper-babel-20260927` @ `d45a251` | 2 files, source intake only, no vendored code | `git diff origin/main d45a251` |
| UFA entry | SUBMITTED, `b968c199-…`, `missing_for_judging=[build.demo_video_url]` | server receipt, HTTP 200 |
| JEV key | requested, not received | — |
| Tenki / Mitosis | sources frozen (BP-0007); execution 0 | BP-0007 observed list |
| Games | 0 JEV, 0 baseline, 0 scripted on remote | `results.json` |

**Numbering changed.**
- v1 planned BP-0007…0016. Another session used BP-0007 and BP-0008 for the sponsor source freeze.
- The code assigns each new breakpoint the next number after the highest existing file, so the numbers below are **expected**, not reserved.
- BP-0001…0008 have no atom roots. They enter the MMR as `LEGACY_SINGLE_ATOM` entries when BP-0009 is created.

**Single writer rule.** Only one session pushes to `main` while games run. The harness stops if a push fails. Recover with `git pull --rebase && git push`, then continue.

---

## 1. Arms (unified names; replaces v1's J0/V0/L0)

| Arm | Decider | State | Counts toward Performance |
|---|---|---|---|
| R0 | scripted sweep | none | no (`provider: none`) |
| J0 | JEV | perception_v1 (frame → JSON) | yes, if the arm is chosen as the counted arm |
| J1 | JEV | J0 + Anticube + ECA danger + Minesweeper constraint field | yes, if the arm is chosen as the counted arm |
| J2 | JEV | J1 + path summaries / ΔG* features + recovered memory | yes, if the arm is chosen as the counted arm |
| O* | OpenJev | same schema as the J arm it mirrors | no (`provider: openjev`, not TypeSafe) |
| L0 | LLM via system-one-adapter | **identical state to the counted J arm** | baseline |

**Counted arm.** It is chosen at BP-0014 from OpenJev development runs, before any JEV key is used. It is written into the breakpoint before the counted games, so the choice is not made after seeing JEV results. Default: J1. J2 only if memory consumption is already working (BP-0018).

**Rules that hold in every arm:**
- The decider always picks the move.
- The state never contains `recommended_move`.
- If an invalid choice is replaced, the log records `proposed`, `executed` and `fallback_reason` separately. The harness already does this.

---

## 2. Breakpoint chain

Every breakpoint follows the same pattern:
1. Its atoms (FCOs) are hashed.
2. The atoms roll up into an FMO root.
3. That root is appended to `governance/MMR_LEDGER.json`.
4. `scripts/verify_breakpoints.py` recomputes everything from scratch.

A failed gate is still committed, with its FAIL state, and a successor breakpoint follows.

Every breakpoint is `SIGNATURE_STATE=NOT_SIGNED` unless signing is actually executed (see BP-0020).

### Critical path (never cut)

| BP | Name | Atoms (FCOs) | FCG edges | Exit gate (measured) | Priority / slot |
|---|---|---|---|---|---|
| **0009** | RUNTIME_DETERMINISM | runtime dataset V2 (ale-py wheel files incl. bundled ROM, interpreter), smoke receipt, entry receipt, **code-commit atom for the landed patch** | `SUPERSEDES` BP-0005 runtime freeze; `EXECUTED_WITH` | patch commit exists on `origin/main`; seeds 1–5 trajectory hashes identical across 2 spawned processes | P0–P1 · Sun AM |
| **0010** | HARNESS_AUTOPUSH | harness code, `results.json`, 5 R0 traces | `RESULTS_IN`, `PUBLISHED_TO git:main` | 5 R0 runs, each with its own `results: run n,` commit on `origin/main`; trace hashes match | P2 · Sun AM |
| **0011** | NATIVE_KERNELS | `state_address` (rank/unrank), `eca_step(row, rule)`, `constraint_field`; CellPyLib cross-check receipt; SAT-oracle check receipt; PR #1 intake JSON (by hash, from `d45a251`) | `DERIVED_FROM` intake sources (reference only; no vendored code); `VALIDATED_AGAINST` CellPyLib@743e936, Minesweeper-Solver-SAT@9bdb1c3 | (a) `unrank(rank(s)) == s` on ≥ 10k random states, with address and SHA-256 recorded as separate fields; (b) our ECA output equals CellPyLib's, byte for byte, for rules {0,30,54,90,110,150,184,255} on frozen initial conditions and T steps (target REPLAY_LEVEL_4); (c) on ≥ 1k synthetic boards, every cell our kernel calls SAFE or NONSAFE matches the SAT oracle | P3 · Sun PM |
| **0012** | VITHIA_PREPROCESSOR | `preprocess.py` (atoms → Anticube → ECA danger → constraint field → path summaries), frozen test frames, J1/J2 state schema | `OBSERVED_AS`, `CONSTRAINS`, `CANDIDATE_SUCCESSOR` | ≥ 20 frozen frames hand-checked; per-frame preprocessing p50/p95 recorded; state token size recorded; unit test asserts no `recommended_move` key; each successor records `parent_state_id, rule/version, step, action, predicted, observed, prediction_error` | P3 · Sun PM |
| **0015** | JEV_COUNTED | 5 JEV traces (counted arm), request/response identities, served model id | `DECIDED_BY` JEVReceipt | 5 runs with `provider: typesafe`, seeds 1–5, each pushed before the next starts; `served_model` taken from the response | P4 · Mon (depends on key) |
| **0016** | LLM_BASELINE | 5 L0 traces, adapter version, provider model id, usage | `COMPARED_WITH` BP-0015 runs | 5 runs, same seeds, same state encoding as the counted arm; cost from `usage` × a cited price, or omitted | P5 · Mon |
| **0020** | JUDGE_READY_SEAL | README judge section, final `results.json`, final entry receipt, public-URL check receipt, optional signature | `SUBMITTED_AS` entry `b968c199` | the checklist in §4 passes on the **public** URL; entry resubmitted with `demo_video_url`; server returns `ok: true` with empty `missing_for_judging` | P8–P10 · Mon ≤ 23:00 PT |

### Sponsor receipts (needed for the claims already in the entry)

| BP | Name | Atoms | Exit gate |
|---|---|---|---|
| **0017** | TENKI_RECEIPT | sandbox id, runtime identity, code commit, `pytest` log, ECA replay digest, local digest | real sandbox created; `pytest` passes inside it; ECA replay digest equals the local one (report the REPLAY_LEVEL actually observed); then ≥ 1 fixed-seed game or sweep run inside Tenki. Per BP-0007 terms: publish results about our agent only, **no Tenki infrastructure timings**. |
| **0018** | MITOSIS_RECEIPT | `cortex_remember` receipt (returned `universal_id`), `cortex_ask` receipt (returned evidence), native FCO id + content hash, consuming episode id | real remember → ask round trip; one episode/wave's parameters (τ, H, ħ or strategy evidence) come **only** from the Mitosis result; ablation: the same seed with and without memory, recording whether decisions differ. "Load-bearing" is claimed only if they differ. |

**Entry honesty rule.** The entry already names both sponsors. If BP-0017 or BP-0018 is not SUPPORTED by Mon 22:00 PT, the entry is resubmitted with that sponsor set to `false`, or with wording that matches what actually ran. It is not left claiming unexecuted use.

### Provider-neutral layer (minimal, from the architecture addendum)

| BP | Name | Atoms | Exit gate |
|---|---|---|---|
| **0013** | PROVIDER_ADAPTERS + REPLAY | `MemoryBackend` (SeedGraphBackend: remember/ask/recall/get/manifest on FCO files), `ExecutionBackend` (LocalReplayBackend), `DecisionBackend` (wraps existing deciders), `replay_manifest.schema.json`, `replay.sh`, CPU `Dockerfile` + lockfile | `./replay.sh run_0001` re-plays an R0 run from its manifest and emits a **new** ExecutionReceiptFCO with a `REPLAY_OF` edge; R0/ALE should reach REPLAY_LEVEL_4 (report what is observed). No framework rewrite: adapters wrap the existing code. No ROM bytes in the image; `ale-py` installs its own. |

Adapter mapping. The two identities are kept side by side; they are not claimed equivalent:

- **Memory:** `SeedGraphBackend` is native; `MitosisCortexBackend` stores `native_fco_id + native_content_hash + mitosis_universal_id`.
- **Execution:** `LocalReplayBackend` is native; `TenkiBackend` receives the same spec and produces a comparison receipt.
- **Decision:** `TypeSafeJEV`, `OpenJev`, and `LLMSystemOne` are implemented now. `LocalMLX` and `LocalGGUF` are added only if used. `probabilities=NOT_AVAILABLE` wherever a backend returns none.

SeedGraph use does **not** count as Mitosis use, and local replay does **not** count as Tenki use.

### Development and research (cut first)

| BP | Name | Exit gate |
|---|---|---|
| **0014** | OPENJEV_DEV + ARM_SELECTION | OpenJev runtime manifest recorded: repo revision, weight-file hashes, quantization, engine and version, helper settings, hardware. J0 vs J1 (and J2 if ready) on seeds 1–5, all labeled non-JEV. **Counted arm written into the breakpoint before BP-0015.** |
| **0019** | CA_RULIOLOGY | the v1 §3 study (256/88 rules, pre-registered H1–H4) on the native ECA kernel. May overlap with PR #1 reference checks. |

**Cut order if time runs short:**
1. BP-0019
2. BP-0014's J2 arm
3. BP-0013's Dockerfile (keep the manifest and `replay.sh`)
4. BP-0018's ablation (keep the round trip)

Never cut: 0009, 0010, 0015, 0016, 0020.

---

## 3. Frozen definitions (not changed by this update)

- **G\*** = U* − τ·H_norm.
  - U* = realized danger burden at the successor position.
  - H_norm = normalized Shannon entropy of the decider's returned probabilities.
- **ΔG\*** = G*(decider) − G*(reference decider on the same state).
- Claim ceiling: `DIMENSIONLESS_INFORMATION_STATE_DIAGNOSTIC`. `THERMODYNAMIC_GIBBS_CLAIM=NO`.
- The internal `delta_g_vector` (Δexpected cost, Δentropy, safe-path mass, concentration, Δuncertainty) is logged alongside the scalar and does not replace it.
- Library of Babel, Minesweeper, Feynman–Kac and CA sources are prior art. They do not define Vithia or ΔG*.

---

## 4. Judge-ready checklist (BP-0020 gate, checked on the public URL)

**Automated:** record each as PASS/FAIL in `evidence/judge_check/JUDGE_CHECK.json`.

- `PUBLIC_REPO_ACCESS`: anonymous `git ls-remote` and a raw README fetch.
- `DEFAULT_BRANCH=main`.
- `REMOTE_HEAD` equals the tested commit.
- `RESULTS_JSON` at the repo root passes the validator: p95 ≥ p50, calls ≤ steps, frames ≥ steps, every required `score` present.
- `JEV_RUN_COUNT` (`provider: typesafe`) ≥ 5, or recorded as `JEV_ACCESS_NOT_RECEIVED`.
- `BASELINE_RUN_COUNT` ≥ 5.
- Run numbers are contiguous with the `results: run n` commit history, so no run was silently removed.
- Clean-checkout reproduction: `git clone` → `pip install -r requirements.txt` → `pytest` → `run_games.py --dry-run --decider scripted --seeds 1`.
- Pins: `ale-py==0.12.1`, `gymnasium==1.3.0`, plus lockfile if BP-0013 lands.
- Secret scan passes, and gitleaks if available.
- Sponsor wording in the README and entry matches the SUPPORTED state of BP-0017/0018.
- The demo URL resolves publicly.
- The entry's `repo_url` equals `https://github.com/biobitworks/jev-space-invaders` exactly.

`JUDGE_READY=YES` only if every mandatory item passes.

**README top section**, before any governance material:
1. Project, pitch, and the 5-line architecture (Atari → state extraction → CA/Minesweeper hazard inference → path evidence → **JEV decision** → ALE action).
2. Reproduce commands.
3. The `results.json` link and a comparison table.
4. Sponsor sentences, taken from their receipts.
5. Links to `governance/` and `evidence/`.

**Signing.** Sign only inside Byron's local signing boundary, and only if the key is available there. The private key never enters git, Docker, Tenki, Mitosis, JEV requests, or model context. Otherwise `SIGNATURE_STATE=NOT_SIGNED` and `PUBLIC_KEY_FINGERPRINT=NOT_COMPUTED`.

---

## 5. Schedule

| When (PT) | Work |
|---|---|
| Sun AM | Land patch → BP-0009 → R0 games → BP-0010 |
| Sun PM | BP-0011 native kernels → BP-0012 preprocessor; Tenki/Mitosis sign-ups and first smoke calls |
| Sun night | BP-0013 replay (minimal); BP-0014 if OpenJev hardware is ready; BP-0017 Tenki receipt |
| Mon AM–PM | BP-0015 as soon as the key arrives; BP-0016; BP-0018 Mitosis |
| Mon PM | Record demo (lead with JEV vs LLM latency plus the danger overlay); post tagging UFA |
| Mon ≤ 23:00 | BP-0020 checklist → resubmit entry with demo URL and final commit |

**Risk.** If no JEV key arrives by Mon 18:00 PT, the entry is judged on non-counted runs only. Email the organizers Sunday referencing entry `b968c199` and `needs_jev_access: true`.

---

## 6. Open items only Byron can resolve

1. Apply and push the patch (Claude cannot push to the repo).
2. OpenJev hardware (MLX 4-bit on Mac / GGUF on 24 GB / FP8 on 80 GB), or skip BP-0014.
3. Baseline provider and key.
4. Tenki and Mitosis account credentials, kept in the local environment only.
5. Whether a signing key exists locally for BP-0020.
6. The demo video URL, by Monday.
