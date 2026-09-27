# Vithia-Space — UFA JEV Bake-Off 2026

Public, reproducible UFA arena branch of the Vithia model family. Competition-facing code and measured results are public; credentials and unrelated proprietary Vithia architecture are not.

## Current state

- Registration: SUBMITTED (entry `b968c199…`, receipt in `evidence/entry/`); demo video still required
- Track: pilot. JEV access: requested. In person Sep 30: yes
- Sponsor stack (Mitosis Cortex, Tenki sandboxes): PROPOSED, not yet implemented
- Counted JEV games: see `results.json` (`provider: "typesafe"` runs only)
- Non-JEV runs (`provider: "none"` scripted, `provider: "openjev"`) are labeled and do not count toward Performance

## Competition contract

- JEV must make the core decisions.
- Public repo must run from this README.
- At least 5 fixed-seed JEV games and 5 comparable LLM baseline games.
- Append every game to root results.json; commit and push immediately.
- Measurements come from environment/API/runtime, never estimates.

## Proposed winning lane

Pilot: JEV chooses one of NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE from compact game state. The identical decision interface is run through TypeSafe's System One LLM adapter for the baseline.

The proposed originality layer is confidence-aware temporal control: state includes current RAM plus deterministic deltas from recent frames; low-confidence behavior is explicit and measured rather than hidden.

## Frozen runtime-source dataset

The starting executable-evidence dataset is `VITHIA_SPACE_RUNTIME_SOURCE_FREEZE_20260927_001`, committed by FMO root `28c9beac8c617df2c8409b50d45ee6240408455c53db5b845261fb4005171a81`. Exact third-party downloaded bytes remain in an ignored local cache; the public repository contains hashes, provenance state, and a verifier. The Space Invaders ROM is not present in this freeze. The runtime breakpoint (`scripts/bp_runtime.py`) supersedes it with `evidence/runtime_v2/` (ale-py runtime, bundled ROM hashed).

Runtime source is treated as data: dependency bytes, configuration, assets, RNG behavior, wrappers, and generated transitions can all influence the experiment. Unknown runtime information remains explicit UNKNOWN/NOT_VERIFIED evidence.

## Setup

Python 3.10+. The Space Invaders ROM ships inside the `ale-py` wheel; no separate download is needed.

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # keys go here only; never commit .env

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
    python scripts/verify_breakpoints.py      # recomputes every breakpoint root and the MMR

## Vithia lineage and secrecy boundary

Vithia-Space is a bounded competition/evaluation branch of the Vithia family. JEV receives only the minimum game state needed for action selection. API keys, private prompts, patent-sensitive notes, and unrelated Vithia architecture stay outside Git and outside JEV inputs.

The TypeSafe license gate in `TYPESAFE_LICENSE_GATE.md` must pass before the first JEV call.

## Governance

governance/breakpoints is append-only project state. Hashes identify bytes; they do not establish correctness. No signature or Merkle/MMR commitment is claimed unless actually executed and verified.
