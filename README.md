# Vithia-Space — UFA JEV Bake-Off 2026

Public, reproducible UFA arena branch of the Vithia model family. Competition-facing code and measured results are public; credentials and unrelated proprietary Vithia architecture are not.

## Current state

- Registration: NOT SUBMITTED
- Track: UNRESOLVED (pilot proposed; human choice required)
- JEV access: UNRESOLVED
- Sponsor stack: UNRESOLVED
- Demo video: NOT PRESENT
- Executed JEV games: 0/5
- Executed LLM baseline games: 0/5
- results.json: schema initialized; contains no fabricated scores

## Competition contract

- JEV must make the core decisions.
- Public repo must run from this README.
- At least 5 fixed-seed JEV games and 5 comparable LLM baseline games.
- Append every game to root results.json; commit and push immediately.
- Measurements come from environment/API/runtime, never estimates.

## Proposed winning lane

Pilot: JEV chooses one of NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE from compact game state. The identical decision interface is run through TypeSafe's System One LLM adapter for the baseline.

The proposed originality layer is confidence-aware temporal control: state includes current RAM plus deterministic deltas from recent frames; low-confidence behavior is explicit and measured rather than hidden.

## Setup

Python 3.10+; create a virtualenv, install requirements.txt, and copy .env.example to .env. Add keys only to .env; never commit it.

Atari ROM installation/licensing must follow ALE/Gymnasium instructions for the executing machine.

## Reproducibility

Run: python scripts/validate_results.py
Run: python -m pytest -q

Game execution remains NOT_EXECUTED until credentials and track are resolved.

## Vithia lineage and secrecy boundary

Vithia-Space is a bounded competition/evaluation branch of the Vithia family. JEV receives only the minimum game state needed for action selection. API keys, private prompts, patent-sensitive notes, and unrelated Vithia architecture stay outside Git and outside JEV inputs.

The TypeSafe license gate in `TYPESAFE_LICENSE_GATE.md` must pass before the first JEV call.

## Governance

governance/breakpoints is append-only project state. Hashes identify bytes; they do not establish correctness. No signature or Merkle/MMR commitment is claimed unless actually executed and verified.
