# Vithia-Space — UFA JEV Bake-Off 2026

Public, reproducible UFA arena branch of the Vithia model family. Competition-facing code and measured results are public; credentials and unrelated proprietary Vithia architecture are not.

## Judge reproducibility update

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
- Tenki and Mitosis are **not required** for the judge-critical path in this successor. Current state of that OpenJEV engineering stage: Tenki **DEFERRED_NOT_REQUIRED_FOR_THIS_STAGE**; Mitosis **OFF_NOT_REQUIRED_FOR_THIS_STAGE**. Later post-submission Mitosis and Tenki results (artifact reconstruction PASS, strict environment replay FAIL) are recorded separately in the judge update.
- Qualified competition governance uses the `UFA-JEV-COMP-BP-*` namespace; historical identifiers and predecessor breakpoints remain immutable.

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
