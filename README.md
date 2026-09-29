# Vithia-Space — UFA JEV Bake-Off 2026

Public, reproducible UFA arena branch of the Vithia model family. Competition-facing code and measured results are public; credentials and unrelated proprietary Vithia architecture are not.

## Post-submission judge reproducibility update

The accepted UFA submission remains frozen. A post-submission reproducibility successor for independent judge review is available at:

- PR #9: https://github.com/biobitworks/jev-space-invaders/pull/9
- Judge branch: https://github.com/biobitworks/jev-space-invaders/tree/postsubmission/judge-reproducibility-v02
- Reproducibility update: https://github.com/biobitworks/jev-space-invaders/blob/postsubmission/judge-reproducibility-v02/docs/JUDGE_REPRODUCIBILITY_UPDATE_V01.md
- Judge agent prompt: https://github.com/biobitworks/jev-space-invaders/blob/postsubmission/judge-reproducibility-v02/docs/JUDGE_AGENT_PROMPT_V01.md

This update does not replace or rewrite the accepted competition entry or qualified historical evidence.

## Demo video

**Public demo video:** https://youtu.be/4BuR_NnJAsM

**Submission-record video URL:** https://youtu.be/Yo-WfJVJO-Q — currently recorded as private to unauthenticated viewers in the post-submission verification branch. Use the public demo above unless/until the submission-record video is made Unlisted/Public.

## Current verified competition state

- Registration: **SUBMITTED** (entry b968c199...). Publicly viewable fallback demo: https://youtu.be/4BuR_NnJAsM. The submission-record URL `Yo-WfJVJO-Q` was observed private to unauthenticated viewers during post-submission verification.
- Track: **pilot**. Counted hosted TypeSafe JEV runs remain **0**; the repository is now **READY_BYO_TYPESAFE_API_KEY** and fails closed with `BLOCKED_MISSING_TYPESAFE_API_KEY` rather than substituting another backend.
- Qualified competition evidence remains **UFA-JEV-COMP-BP-0017**. The later replay/context work is recorded separately as **UFA-JEV-COMP-BP-0018-ENGINEERING-SUCCESSOR** and is **not** promoted to qualified MMR admission.
- Local Ollama comparator: `llama3.2:3b`, five fixed seeds executed; scores: **270, 270, 270, 270, 270**. This is a local comparator, not counted hosted JEV.
- OpenJEV engineering lane: **PASS_BOUNDED_LOCAL** with `openjev/openjev-MLX-4bit`. In the matched 3-seed × 3-step smoke, Vithia L1 changed decision p50 from **5626.834 ms** to **4725.3426 ms** (Δ **-901.4914 ms**), while p95 changed from **6176.3331 ms** to **7057.1172 ms** (Δ **+880.7841 ms**) and score remained **0 → 0**. This is bounded engineering evidence, not a hosted-JEV performance claim.
- Context sweep: **PASS_BOUNDED**. `L0` was the minimum/best-p50 context in the recorded sweep; the adaptive Anticube/ΔG* candidate was **TESTED_NOT_WINNER**.
- Replay proof: `ReplaySeedFCO` **PASS**, replay-from-start **PASS**, step-hash equality **PASS**, final-MMR equality **PASS**. Random-access restore support exists, but arbitrary restored-step hash equality is **not claimed**.
- System One adapter: installed/ready for comparator use; no new provider-backed official baseline run is claimed here.
- Tenki and Mitosis are **not required** for the judge-critical path in this successor. Current successor state: Tenki **DEFERRED_NOT_REQUIRED_FOR_THIS_STAGE**; Mitosis **OFF_NOT_REQUIRED_FOR_THIS_STAGE**.
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

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # keys go here only; never commit .env

## Judge quick path

1. Install the live demo runtime:

       python -m venv .venv && source .venv/bin/activate
       pip install -r live_demo/requirements.txt

2. Provide your own TypeSafe key in the shell only:

       export TYPESAFE_API_KEY=<judge-key>

3. Run the real JEV path:

       python -m live_demo.run --mode 1p --preprocessor vithia --decider jev --render terminal --headless --run-class COMPETITION_JEV

If `TYPESAFE_API_KEY` is absent the runner exits with
`JEV_API=BLOCKED_MISSING_TYPESAFE_API_KEY` and does not substitute OpenJEV,
Ollama, Tenki, Mitosis, or any operator credential.

## Play and record (results.json is regenerated this way)

Every game is appended to `results.json`, its per-step trace is written to `runs/`, and both are committed and pushed **before the next game starts**. Run from a clean worktree on the default branch.

    python scripts/run_games.py --decider scripted --seeds 1 2 3 4 5     # harness check, non-JEV
    python scripts/run_games.py --decider jev --seeds 1 2 3 4 5          # TYPESAFE_API_KEY
    python scripts/run_games.py --decider llm --provider anthropic --model claude-haiku-4-5 --seeds 1 2 3 4 5
    python scripts/run_games.py --decider openjev --base-url http://127.0.0.1:3000 --seeds 1 2 3 4 5

Deciders:

- **JEV and OpenJev** get the same request: one `choice` question over `NOOP FIRE RIGHT LEFT RIGHTFIRE LEFTFIRE`.
- **The LLM baseline** gets the identical question and state through `system-one-adapter`.
- **State** is parsed from the RGB frame into JSON (`src/perception.py`); raw RAM is never sent.

Try it without git using `--dry-run --results /tmp/results.json`.

## Verify

    python -m pytest -q
    python scripts/validate_results.py
    python scripts/verify_breakpoints.py      # legacy chain; currently FAILs on BP-0010 mutable results.json
    python scripts/verify_competition_lineage.py  # qualified UFA-JEV-COMP chain; must PASS

## Vithia lineage and secrecy boundary

Vithia-Space is a bounded competition/evaluation branch of the Vithia family. JEV receives only the minimum game state needed for action selection. API keys, private prompts, patent-sensitive notes, and unrelated Vithia architecture stay outside Git and outside JEV inputs.

The TypeSafe license gate in `TYPESAFE_LICENSE_GATE.md` must pass before the first JEV call.

## Governance

Historical governance/breakpoints files are append-only. After a verified parallel-branch identifier collision, new competition occurrences use the qualified UFA-JEV-COMP-BP-* namespace and governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json. The competition and research predecessor MMRs remain separate commitments; they have not been concatenated or retroactively reconverged. Hashes identify bytes; they do not establish correctness, causality, or scientific validity.
