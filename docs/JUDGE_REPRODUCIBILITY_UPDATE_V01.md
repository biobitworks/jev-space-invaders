# Vithia-Space — Post-Submission Judge Reproducibility Update V01

> This document is a **post-submission** reproducibility successor. It does **not** replace or rewrite the accepted UFA entry, the qualified competition lineage, the submitted gameplay, or any historical breakpoint.

## 30-second orientation

| Question | Answer |
|---|---|
| What is Vithia-Space? | A state preprocessor and claim gate for the Space Invaders arena. Vithia turns the game/evidence state into a compact, hash-committed context and decides which claims that evidence supports; a *decider* (hosted JEV, local OpenJEV, an Ollama model, or a scripted policy) then picks the move or action. The deciders are interchangeable; the gate is not a model. |
| What was originally submitted? | UFA entry `b968c199-5d7e-4228-b8fe-b0003b7ab94f`, source commit `4c943a92e84d0fb2cd3d01e4fdf15a10991eda71`, a 240-frame real ALE playthrough (MMR root `e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74`) and the qualified `UFA-JEV-COMP` lineage (17 breakpoints, root `2ade9c6159e02e0275a4746b400b477546ccde76cd769305afe0351b73b29f91`). The last recorded organizer response was `ok=true`, `missing_for_judging=[]` ([receipt](../evidence/post_submission/e2e/FINAL_SUBMISSION_VERIFICATION_RECEIPT.json)). |
| What is post-submission? | Everything under `evidence/post_submission/`, `evidence/fcg_seeds/`, `evidence/fcg_sessions/`, the Doctor3 tooling in `tools/`, and these judge documents. None of it is pre-deadline evidence. |
| Where is the public demo? | https://youtu.be/4BuR_NnJAsM (public) and the submission-record video https://youtu.be/Yo-WfJVJO-Q — both were checked as a signed-out viewer on 2026-09-29 and both played. Re-check; visibility is controlled by the owner. |
| How do I run it? | [Prerequisites](#prerequisites), then [Path A](#path-a--no-key-no-write-access). |
| Without sponsor credentials? | Yes — Path A needs no Mitosis, Tenki, TypeSafe, Anthropic, OpenAI or AWS credential. |
| With my own TypeSafe key? | [Path B](#path-b--hosted-typesafe-jev-optional-judge-provided-key). |
| Where are the receipts? | [Receipt map](#receipt-map). |
| What is PASS vs BLOCKED? | [States](#states-exactly-as-recorded). A blocked or unavailable state is never rewritten as PASS. |
| What is not claimed? | [Not claimed](#what-is-not-claimed). |

## Canonical identity

- Repository: `https://github.com/biobitworks/jev-space-invaders`
- This branch: `postsubmission/judge-reproducibility-v02` (pull request #9)
- Doctor3 base: `postsubmission/vithia-doctor3-v01`
- Frozen submitted source commit: `4c943a92e84d0fb2cd3d01e4fdf15a10991eda71`
- Frozen Seed FCO: `evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json`, root `sha256:45d04e0d2da5f0c1255844b011bb2576320e1ff5517f0e38d8e79b8899a88bc8`

This document deliberately does not hard-code a "current" commit SHA. Record `git rev-parse HEAD` in your own receipt.

Hashes and Merkle/MMR commitments establish byte identity, ordered custody, and reconstruction of the declared objects. They do not by themselves establish scientific correctness, causality, or semantic equivalence.

## Prerequisites

- `git` (Git LFS is **not** required; set `GIT_LFS_SKIP_SMUDGE=1` so a clone never downloads large historical data files)
- Python 3.10+ available as `python3`
- Python package `cryptography` (checkpoint signing)
- [Gum](https://github.com/charmbracelet/gum) — only for the interactive Doctor3 UI in step A3 (`brew install gum` on macOS; see the Gum page for Linux)
- Optional: [Ollama](https://ollama.com) with at least one **already-installed** local text model; nothing is downloaded for you

No API key is required for Path A.

## Clone and set up

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch postsubmission/judge-reproducibility-v02 https://github.com/biobitworks/jev-space-invaders.git
cd jev-space-invaders
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r live_demo/requirements.txt cryptography
```

## Path A — no key, no write access

**A1. Independently verify the frozen objects (no Gum, no model).**

```bash
python3 scripts/verify_final_playthrough_custody_v2.py evidence/competition/final_execution/frames   # PLAYTHROUGH_VERIFY=PASS, 240 frames
python3 scripts/verify_e2e_breakpoints.py                                                            # E2E_BREAKPOINT_VERIFY=PASS
python3 scripts/secret_scan.py                                                                        # SECRET_SCAN=PASS
```

**A2. Discovery-driven local verification (recommended).** This discovers the local models that are actually installed (it never downloads one and never assumes a model name), verifies the Seed FCO and pinned source, and runs *one* Doctor3 session in which every discovered model — plus a scripted reference lane — consumes the **same** Vithia verified context. It writes nothing to git and needs no push access.

```bash
python3 tools/verify_doctor3_ollama_local.py --auto-lanes --local-only
```

- With no local model installed it runs the scripted lane only and reports that no model was discovered.
- OpenJEV is included only if it is already running and positively identified by `scripts/openjev_runtime.py status`. Add `--start-openjev` only if you already have the OpenJEV weights; it starts the existing local runtime and never downloads.
- Hosted JEV, Mitosis and Tenki are not used. Their states are reported as `BLOCKED` / `NOT_EXECUTED`.

**A3. Interactive Doctor3 (Gum UI).**

```bash
bash tools/vithia_doctor3.sh --seed-fco evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json --local-only
```

`--local-only` uses real providers and real signing but performs no commit and no push. Suggested choices: *generate a new local Ed25519 identity* (or *anonymous verifier*); skip every credential prompt; pick a decider. The "local Ollama" choice uses the model named by the `OLLAMA_MODEL` environment variable (default `llama3.2:3b`); if that model is not installed the lane is reported `BLOCKED` — it never falls back to another backend. Use A2 to have the models discovered for you. Tenki execution needs a pushed commit, so it is `NOT_EXECUTED` in `--local-only` mode.

The private signing key is written to `~/.vithia/identities/` (mode 600), outside the repository. Only the public key, its fingerprint and the signature enter evidence.

**A4. The live demo runner (informational).**

```bash
python3 -m live_demo.probe_integrations
python3 -m live_demo.run --mode 1p --seed 3 --steps 3 --player0-preprocessor vithia --player0-decider scripted --headless --results-path /tmp/judge_live_demo_results.json
```

`--results-path` keeps the run from modifying the tracked `results.json` (which would make Doctor3 refuse a dirty tree). Caution: for a model decider (`--player0-decider ollama:<model from ollama list>`) the runner can fall back to `NOOP` when a model request fails and still print `terminal_acceptance=PASS`; check `fallback_actions` in the resulting row — anything above 0 means those steps were not decided by the model. The Doctor3 lanes in A2/A3 have no such silent fallback.

## Path B — hosted TypeSafe JEV (optional, judge-provided key)

Hosted JEV is intentionally fail-closed. With your own authorized key, set it in the process environment only:

```bash
export TYPESAFE_API_KEY=<your own key>
python3 -m live_demo.run --mode 1p --preprocessor vithia --decider jev --render terminal --headless --run-class COMPETITION_JEV --results-path /tmp/judge_jev_results.json
```

Without `TYPESAFE_API_KEY` the runner prints `JEV_API=BLOCKED_MISSING_TYPESAFE_API_KEY` and does not substitute OpenJEV, Ollama, Tenki, Mitosis or any other backend.

## OpenJEV

Do not guess an OpenJEV port and do not infer identity from an open port. The authoritative endpoint is the one recorded by the repository helper:

```bash
python3 scripts/openjev_runtime.py status
```

If it fails with `FileNotFoundError` for `runtime_state.json`, the runtime has never been started: record `OPENJEV=NOT_RUNNING`. If you already have the local weights, `python3 scripts/openjev_runtime.py serve` starts the runtime from them (it never downloads; `download` is a separate, explicit subcommand) and records the endpoint that `status` then reports.

## Multi-lane semantics

In a multi-lane Doctor3 session every lane consumes the identical `VITHIA_VERIFIED_CONTEXT_ROOT` (reported as `SAME_INPUT_CONTEXT_ROOT_ACROSS_LANES=YES`) and the same frozen, hashed prompt profile (`neutral_v1`). Each lane gets its own Decision, Action-Execution and Outcome FCO. A model that selects a claim above the evidence ceiling is preserved unmodified and the claim gate blocks it:

```text
DECISION_SUPPORTED_BY_CONTEXT=NO
ACTION_EXECUTION=BLOCKED
OUTCOME=BLOCKED
LANES_CLAIM_GATE_INTEGRITY=PASS      # no unsupported claim was executed
```

That is a model observation, not an infrastructure failure. Do not tune a model and re-run to obtain a green answer.

## States exactly as recorded

| Item | State | Receipt |
|---|---|---|
| Submitted 240-frame playthrough MMR | `PASS` (240 frames, root `e55a47a7…`) | `evidence/competition/final_execution/frames/PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json` |
| ReplaySeedFCO (bounded OpenJEV engineering run, 3 seeds × 3 steps — a *different object* from the submitted playthrough) | `PASS` (replay-from-start, step-hash, final-MMR) | `evidence/competition/replay_seed_adaptive/REPLAY_SEED_ADAPTIVE_SUCCESSOR_RECEIPT.json` |
| Random-access replay | `RESTORE_SUPPORTED_STEP_HASH_NOT_CLAIMED` | same receipt |
| Artifact reconstruction of the submitted playthrough in a fresh Tenki sandbox | `PASS` | `evidence/post_submission/e2e/TENKI_VERIFICATION_FCO.json` |
| Strict environment replay of the submitted playthrough | **`FAIL`** — first mismatch frame 0, `PNG_BYTES` | `evidence/post_submission/e2e/LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json`, `TENKI_VERIFICATION_FCO.json` |
| PNG bytes | **`FAIL`** for 240/240 frames while pixels, scores, lives, actions, frame roots and the final MMR all match | `evidence/post_submission/e2e/PNG_ENCODING_MISMATCH_INVESTIGATION.json` (encoder drift only) |
| Earlier, overstated Tenki artifact claim | superseded by a hash-bound correction; the original is preserved | `evidence/post_submission/e2e/TENKI_CLAIM_CORRECTION_FCO.json` |
| Hosted TypeSafe JEV | `NOT_EXECUTED` (no authorized key; fail-closed) | `README.md` |
| OpenJEV (local) | bounded engineering evidence only; not a hosted-JEV claim | `evidence/competition/replay_seed_adaptive/` |
| Mitosis | persistence and exact-ID retrieval `PASS`; no portable-memory claim beyond `PASS_BOUNDED` | `evidence/post_submission/e2e/MITOSIS_VERIFICATION_ANCHOR_FCO.json` |
| Tenki code review of the successor | `BLOCKED` by review-credit exhaustion (billing, not a defect); earlier findings were fixed | `evidence/post_submission/e2e/TENKI_CODE_REVIEW_RECEIPT.json` |
| Qualified lineage verifier (`scripts/verify_competition_lineage.py`) | **`FAIL` (`ATOM_CHANGED`)** on this branch, on `main`, on the submitted commit itself and on the competition branch tip — see below | — |

**About the lineage verifier.** It recomputes each frozen atom's hash from the working tree. `README.md` was edited in the submitted commit itself (to add the demo link) after its atom was frozen, so the verifier reports `ATOM_CHANGED:README.md` at `4c943a92…` and at every later commit; on `main`-derived branches it also reports files under `demo/` and `tests/test_live_demo.py`, which changed afterwards. It passes at commit `494d299` (the last commit before those edits). The 17-breakpoint chain and its root `2ade9c61…` are unchanged and are not rewritten; the custody verifier in A1 passes at the submitted commit.

## Receipt map

- Frozen submission and lineage: `evidence/competition/`, `governance/lineage/`
- Frozen Seed FCO: `evidence/fcg_seeds/`
- End-to-end successor (Vithia → Mitosis → Tenki → verified context → decider → outcome): `evidence/post_submission/e2e/` (start with `VITHIA_MITOSIS_TENKI_E2E_FINAL_RECEIPT.json` and `BREAKPOINT_VERIFICATION_MATRIX.json`)
- Doctor3 sessions (each an append-only, signed Merkle/MMR ledger): `evidence/fcg_sessions/`

## What is NOT claimed

- No claim that hosted TypeSafe JEV was executed, or that any local backend is JEV.
- No claim that strict environment replay passed; it failed on PNG bytes only.
- No claim that a hash, MMR or signature establishes scientific correctness, causality or model correctness.
- No claim that the organizer accepted any post-submission change. Organizer update/upsert semantics are recorded as `NOT_VERIFIED`; no resubmission was sent.
- No claim that Mitosis or Tenki is load-bearing beyond the bounded states above.

## Operator-reported item (no committed receipt)

The operator reported a separate preflight on another machine ("MagicStudio") that verified the seed root, source commit and adapter wiring, and stopped because the requested models were not installed there. **No receipt for it is committed to this repository**, so this document does not use it as evidence. Judges should discover their own local models rather than rely on model names from any other machine.

## Licensing

The repository contains no `LICENSE` file, and GitHub reports the license as unspecified. No open-source license is claimed. Third-party dependencies (for example `gymnasium`, `ale-py`, `cryptography`) carry their own licenses; Atari ROMs and model weights are not distributed in this repository.

## Submission boundary

This GitHub update is ready for judge review as post-submission reproducibility evidence. It is **not** proof that the organizer API accepts a later POST as an update to the accepted entry; the accepted submission remains unchanged.
