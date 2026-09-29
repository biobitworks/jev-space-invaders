# Vithia-Space — UFA JEV Bake-Off 2026

Public, reproducible UFA arena branch of the Vithia model family. Competition-facing code and measured results are public; credentials and unrelated proprietary Vithia architecture are not.

## Judge reproducibility update

Vithia-Space is a state preprocessor and claim gate for the Space Invaders arena: it turns game/evidence state into a compact, hash-committed context and decides which claims that evidence supports, while interchangeable deciders (hosted JEV, local OpenJEV, an Ollama model, a scripted policy) pick the action.

The accepted UFA submission (entry `b968c199-5d7e-4228-b8fe-b0003b7ab94f`, source commit `4c943a92e84d0fb2cd3d01e4fdf15a10991eda71`) is frozen. Everything on the `postsubmission/*` branches is **post-submission** successor evidence, not pre-deadline evidence. Start here (branch `postsubmission/judge-reproducibility-v02`, pull request #9):

- [Judge reproducibility update](docs/JUDGE_REPRODUCIBILITY_UPDATE_V01.md): orientation, prerequisites, exact PASS/FAIL/BLOCKED states, what is not claimed
- [Copy/paste judge agent prompt](docs/JUDGE_AGENT_PROMPT_V01.md)

Verify with no sponsor credential and no write access (after the prerequisites in the update): `python3 tools/verify_doctor3_ollama_local.py --auto-lanes --local-only`. It discovers the local models you actually have, never downloads one, and never substitutes a backend. Hosted TypeSafe JEV is an optional judge-provided-key path and stays `NOT_EXECUTED` without a key.

## Demo video

**Public demo video:** https://youtu.be/4BuR_NnJAsM

**Submission-record video:** https://youtu.be/Yo-WfJVJO-Q

Both were checked as a signed-out viewer on 2026-09-29 and both played (the second was private earlier that day and has since been published). Video visibility is controlled by the owner; if either does not play for you, please report it.

## Current verified competition state

- Registration: **SUBMITTED** (entry b968c199...). Demo videos: https://youtu.be/4BuR_NnJAsM and https://youtu.be/Yo-WfJVJO-Q (both played signed-out on 2026-09-29; the second was briefly private earlier that day).
- Track: **pilot**. Counted hosted TypeSafe JEV runs remain **0**; the repository is now **READY_BYO_TYPESAFE_API_KEY** and fails closed with `BLOCKED_MISSING_TYPESAFE_API_KEY` rather than substituting another backend.
- Qualified competition evidence remains **UFA-JEV-COMP-BP-0017**. The later replay/context work is recorded separately as **UFA-JEV-COMP-BP-0018-ENGINEERING-SUCCESSOR** and is **not** promoted to qualified MMR admission.
- Local Ollama comparator: `llama3.2:3b`, five fixed seeds executed; scores: **270, 270, 270, 270, 270**. This is a local comparator, not counted hosted JEV.
- OpenJEV engineering lane: **PASS_BOUNDED_LOCAL** with `openjev/openjev-MLX-4bit`. In the matched 3-seed × 3-step smoke, Vithia L1 changed decision p50 from **5626.834 ms** to **4725.3426 ms** (Δ **-901.4914 ms**), while p95 changed from **6176.3331 ms** to **7057.1172 ms** (Δ **+880.7841 ms**) and score remained **0 → 0**. This is bounded engineering evidence, not a hosted-JEV performance claim.
- Context sweep: **PASS_BOUNDED**. `L0` was the minimum/best-p50 context in the recorded sweep; the adaptive Anticube/ΔG* candidate was **TESTED_NOT_WINNER**.
- Replay proof (bounded OpenJEV engineering run, 3 seeds × 3 steps): `ReplaySeedFCO` **PASS**, replay-from-start **PASS**, step-hash equality **PASS**, final-MMR equality **PASS**. Random-access restore support exists, but arbitrary restored-step hash equality is **not claimed**. This is a different object from the submitted 240-frame playthrough, whose strict environment replay is **FAIL** on PNG bytes only (pixels, frame roots and final MMR match); see the judge update.
- System One adapter: installed/ready for comparator use; no new provider-backed official baseline run is claimed here.
- Tenki sponsor evidence is real and separated by function: **Tenki Code Review approved public PR #1** (`TENKI_PUBLIC_CODE_REVIEW_EXECUTED`) and the Tenki Sandbox later executed a governed fixed-seed sponsor run. A separate post-submission Tenki review of PR #4 completed with `CHANGES_REQUESTED` (0 high / 2 medium findings); code review is not runtime verification.
- Tenki and Mitosis are **not required** for the judge-critical path in this successor. Current state of that OpenJEV engineering stage: Tenki **DEFERRED_NOT_REQUIRED_FOR_THIS_STAGE**; Mitosis **OFF_NOT_REQUIRED_FOR_THIS_STAGE**. Later post-submission Mitosis and Tenki results (artifact reconstruction PASS, strict environment replay FAIL) are recorded separately in the judge update.
- Qualified competition governance uses the `UFA-JEV-COMP-BP-*` namespace; historical identifiers and predecessor breakpoints remain immutable.

## Sponsor and OpenJEV evidence map

Every sponsor/provider claim below is tied to a public receipt and a Merkle/FMO breakpoint. Qualified competition breakpoints `UFA-JEV-COMP-BP-0001` through `BP-0017` are ordered leaves in `governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json`; the canonical qualified terminal MMR is size **17**, root `2ade9c6159e02e0275a4746b400b477546ccde76cd769305afe0351b73b29f91`.

| Surface | Evidence state | Primary receipt | Breakpoint / commitment | Claim boundary |
|---|---|---|---|---|
| **Hosted TypeSafe JEV** | `NOT_AVAILABLE_NOT_TESTED`; 0 counted hosted-JEV runs because `TYPESAFE_API_KEY` was absent | [HOSTED_JEV_STATE_RECEIPT.json](evidence/competition/access/HOSTED_JEV_STATE_RECEIPT.json), [JEV_ACCESS_RECEIPT.json](evidence/jev/JEV_ACCESS_RECEIPT.json) | [UFA-JEV-COMP-BP-0002](governance/competition/breakpoints/0002-jev-access-openjev-capability-state.json), breakpoint root `d5c57e7a...`, qualified MMR after BP-0002 `b2a572b2...` | Access-state proof only; no hosted-JEV performance claim |
| **OpenJEV local stand-in — capability** | Matched full-probability comparator blocked by readout mismatch; local targeted readout identified | [OPENJEV_MATCHED_COMPARATOR_CAPABILITY_RECEIPT.json](evidence/competition/openjev/OPENJEV_MATCHED_COMPARATOR_CAPABILITY_RECEIPT.json) | Same [BP-0002](governance/competition/breakpoints/0002-jev-access-openjev-capability-state.json) | OpenJEV is not hosted TypeSafe JEV and is never counted as such |
| **OpenJEV local — executed engineering successor** | `PASS_BOUNDED_3_SEEDS_X_3_STEPS`; replay-from-start, step-hash and final-MMR equality PASS | [Replay/context evidence](evidence/competition/replay_seed_adaptive/) | [UFA-JEV-COMP-BP-0018-ENGINEERING-SUCCESSOR](governance/competition/breakpoints/0018-replay-seed-adaptive-context-openjev.json); replay MMR `51938d47...`, size 9; **qualified MMR admission NOT performed** | Bounded post-submission engineering evidence only |
| **Tenki Code Review** | Public PR #1 reviewed and `APPROVED` | [TENKI_CODE_REVIEW_RECEIPT.json](evidence/competition/sponsors/TENKI_CODE_REVIEW_RECEIPT.json) | [UFA-JEV-COMP-BP-0006](governance/competition/breakpoints/0006-tenki-code-review-sponsor-auth.json), breakpoint root `b31471c7...`, qualified MMR after BP-0006 `ccaf186b...` | Code review proof; not runtime proof |
| **Mitosis Cortex** | Directive persisted and retrieved by universal ID; later final evidence summary also remembered/retrieved | [MITOSIS_DIRECTIVE_RECEIPT.json](evidence/competition/mitosis/MITOSIS_DIRECTIVE_RECEIPT.json), [MITOSIS_FINAL_EXECUTION_RECEIPT.json](evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json) | [BP-0007](governance/competition/breakpoints/0007-mitosis-directive-persisted-retrieved.json), root `2de178d3...`, qualified MMR after BP-0007 `5d3da025...`; final Mitosis receipts are also sealed into [BP-0012](governance/competition/breakpoints/0012-final-execution-capture-sponsor-proof-package.json) | Persistence/retrieval supported; no broader portable-memory claim |
| **Tenki Sandbox** | Governed fixed-seed sandbox run executed using Mitosis-selected seed 3; 100 steps / 400 frames / score 15; not counted as JEV | [TENKI_MITOSIS_RUNTIME_RECEIPT.json](evidence/competition/tenki/TENKI_MITOSIS_RUNTIME_RECEIPT.json) | [UFA-JEV-COMP-BP-0008](governance/competition/breakpoints/0008-tenki-sandbox-mitosis-fed-run.json), root `726e1c34...`, qualified MMR after BP-0008 `c930d226...` | Sponsor runtime proof only; not hosted-JEV proof |
| **Final sponsor package** | Final Mitosis receipt sealed; final Tenki access attempt preserved as blocked due invalid/revoked credential | [MITOSIS_FINAL_EXECUTION_RECEIPT.json](evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json), [TENKI_FINAL_EXECUTION_RECEIPT.json](evidence/competition/final_execution/TENKI_FINAL_EXECUTION_RECEIPT.json) | [UFA-JEV-COMP-BP-0012](governance/competition/breakpoints/0012-final-execution-capture-sponsor-proof-package.json), root `6c5036fd...`, qualified MMR after BP-0012 `2108cc21...` | Final receipts preserve both success and blocker states |

The original sponsor source material was independently frozen before execution as FMO root `336efec74f0c742db4c6c671e387f35338f4f6ebface923123be6428f9d28a14` in [SPONSOR_FMO_RECEIPT.json](evidence/sponsor_source/SPONSOR_FMO_RECEIPT.json). That source-freeze proves identity/custody of the Mitosis and Tenki documentation used for planning; it does **not** prove service execution.

**OpenJEV lineage note.** The canonical qualified BP-0017 terminal root is the value in `UFA_JEV_COMP_MMR_LEDGER.json`: `2ade9c6159e02e0275a4746b400b477546ccde76cd769305afe0351b73b29f91`. The later BP-0018 engineering-successor file contains a different predecessor-root field; because BP-0018 explicitly has `qualified_mmr_admission=NOT_PERFORMED`, judges should use the canonical qualified ledger for the competition root and treat BP-0018 only as post-submission engineering evidence.

## Competition contract

- JEV must make the core decisions.
- Public repo must run from this README.
- At least 5 fixed-seed JEV games and 5 comparable LLM baseline games are the target for the official comparison.
- Append every game to root `results.json`; commit and push immediately.
- Measurements come from environment/API/runtime, never estimates.

## Decision lanes and execution state

The application-level decision interface asks a decider to choose one of `NOOP`, `FIRE`, `RIGHT`, `LEFT`, `RIGHTFIRE`, or `LEFTFIRE` from compact game state. Real hosted JEV, System-One LLM comparators, and local OpenJEV are kept as distinct backends with explicit attribution and no silent fallback.

The current public evidence supports a bounded local OpenJEV comparison and a judge-ready bring-your-own-TypeSafe-key path. It does **not** yet support a hosted-JEV versus System-One performance claim because no counted hosted-JEV run has been executed with a TypeSafe key.

## Frozen runtime-source dataset

The starting executable-evidence dataset is `VITHIA_SPACE_RUNTIME_SOURCE_FREEZE_20260927_001`, committed by FMO root `28c9beac8c617df2c8409b50d45ee6240408455c53db5b845261fb4005171a81`. Exact third-party downloaded bytes remain in an ignored local cache; the public repository contains hashes, provenance state, and a verifier. The Space Invaders ROM is not present in this freeze. The runtime breakpoint (`scripts/bp_runtime.py`) supersedes it with `evidence/runtime_v2/` (ale-py runtime, bundled ROM hashed).

Runtime source is treated as data: dependency bytes, configuration, assets, RNG behavior, wrappers, and generated transitions can all influence the experiment. Unknown runtime information remains explicit UNKNOWN/NOT_VERIFIED evidence.

## Setup

Python 3.10+. The Space Invaders ROM ships inside the `ale-py` wheel; no separate download is needed.

    python3 -m venv .venv && source .venv/bin/activate
    python3 -m pip install -r requirements.txt
    cp .env.example .env        # keys go here only; never commit .env

## Judge quick path

1. Install the live demo runtime:

       python3 -m venv .venv && source .venv/bin/activate
       python3 -m pip install -r live_demo/requirements.txt

2. Provide your own TypeSafe key in the shell only:

       export TYPESAFE_API_KEY=<judge-key>

3. Run the real JEV path:

       python3 -m live_demo.run --mode 1p --preprocessor vithia --decider jev --render terminal --headless --run-class COMPETITION_JEV --results-path /tmp/judge_jev_results.json

If `TYPESAFE_API_KEY` is absent the runner exits with
`JEV_API=BLOCKED_MISSING_TYPESAFE_API_KEY` and does not substitute OpenJEV,
Ollama, Tenki, Mitosis, or any operator credential.

## Play and record (results.json is regenerated this way)

Every game is appended to `results.json`, its per-step trace is written to `runs/`, and both are committed and pushed **before the next game starts**. Run from a clean worktree on the default branch.

    python3 scripts/run_games.py --decider scripted --seeds 1 2 3 4 5     # harness check, non-JEV
    python3 scripts/run_games.py --decider jev --seeds 1 2 3 4 5          # TYPESAFE_API_KEY
    python3 scripts/run_games.py --decider llm --provider anthropic --model claude-haiku-4-5 --seeds 1 2 3 4 5
    python3 scripts/run_games.py --decider openjev --base-url <endpoint recorded by: python3 scripts/openjev_runtime.py status> --seeds 1 2 3 4 5   # never guess a port

Deciders:

- **JEV and OpenJev** get the same request: one `choice` question over `NOOP FIRE RIGHT LEFT RIGHTFIRE LEFTFIRE`.
- **The LLM baseline** gets the identical question and state through `system-one-adapter`.
- **State** is parsed from the RGB frame into JSON (`src/perception.py`); raw RAM is never sent.

Try it without git using `--dry-run --results /tmp/results.json`.

## Verify

    python3 -m pytest -q
    python3 scripts/validate_results.py
    python3 scripts/verify_breakpoints.py      # legacy chain; currently FAILs on BP-0010 mutable results.json
    python3 scripts/verify_competition_lineage.py  # reports ATOM_CHANGED on this branch, on main and at the submitted commit
                                                   # (README.md and demo/ files were edited after their atoms were frozen);
                                                   # PASSes at commit 494d299. The chain/root itself is unchanged. See the judge update.

## Vithia lineage and secrecy boundary

Vithia-Space is a bounded competition/evaluation branch of the Vithia family. JEV receives only the minimum game state needed for action selection. API keys, private prompts, patent-sensitive notes, and unrelated Vithia architecture stay outside Git and outside JEV inputs.

The TypeSafe license gate in `TYPESAFE_LICENSE_GATE.md` must pass before the first JEV call.

## Governance

Historical governance/breakpoints files are append-only. After a verified parallel-branch identifier collision, new competition occurrences use the qualified UFA-JEV-COMP-BP-* namespace and governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json. The competition and research predecessor MMRs remain separate commitments; they have not been concatenated or retroactively reconverged. Hashes identify bytes; they do not establish correctness, causality, or scientific validity.
