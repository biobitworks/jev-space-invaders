# Known issue: BP-0010 pinned `results.json` as an immutable atom

`governance/breakpoints/0010-harness-autopush.json` (state `HARNESS_AUTOPUSH_PASS`,
created 2026-09-27T16:52:56Z) includes `results.json` as a `ResultsFCO` atom, hashed
at a point when the file held only the 5 scripted-policy sanity runs.

`results.json` is designed to keep growing: every game played via `run_games.py` /
`scripts/run_games_ollama.py` appends to it and commits+pushes (per README's "Play
and record" section and the competition's own "append every game" rule). Any real
game recorded after BP-0010 was sealed was always going to change the file's bytes,
so `scripts/verify_breakpoints.py` will report `ATOM_CHANGED:results.json` against
BP-0010 from this point forward, permanently. This surfaced for the first time on
2026-09-28 when the first real baseline runs (BP-0052) were appended; no prior
session had appended real (non-sanity) games to `results.json` before this.

## What this is not

This is not evidence that `results.json`'s current content is wrong or tampered.
Independently:

- `scripts/validate_results.py` checks the file's internal schema/counts and PASSes.
- `scripts/verify_episode_mmr.py` recomputes every run's per-decision Merkle root
  from its trace file and PASSes for every run, including the 5 new baseline runs.
- BP-0052 (`m3-baseline-5-complete`) hashes the *current* `results.json` and its
  5 new trace files; that atom root is internally consistent and independently
  verifiable — it just cannot also make BP-0010's older, narrower hash of the same
  path true again, because the file has legitimately grown since.

## Resolution

Breakpoints are append-only by design; BP-0010 is not edited or reissued. This note
is the permanent record: `verify_breakpoints.py` reporting `ATOM_CHANGED:results.json`
against BP-0010 specifically is a known, expected, and documented consequence of
BP-0010's original construction, not a new integrity failure. Future sessions
should treat `BREAKPOINT_VERIFY` as PASS-with-this-one-documented-exception, and
should not add `results.json` as an atom to any future breakpoint pattern that
assumes the file is immutable going forward (BP-0052 records it as a point-in-time
snapshot, which is accurate for that purpose, and will itself face the same fate
once more games are appended after it).
