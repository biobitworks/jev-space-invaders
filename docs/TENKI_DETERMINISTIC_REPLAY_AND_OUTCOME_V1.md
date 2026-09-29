# Tenki deterministic replay + outcome verification v1

This successor answers two distinct questions without model interpretation:

1. **Did the frozen action stream reproduce the recorded environment trajectory?**
2. **Given verified evidence and a frozen outcome predicate, which side won the evaluation or match?**

It does not edit historical traces or receipts.

## One-player replay

Run, for example:

    python scripts/verify_environment_replay_v1.py --run 3 --out /tmp/run3-replay.json

The verifier first checks the trace file SHA-256, every episode leaf and the recorded episode MMR. Only then does it create a fresh ALE environment, reset the frozen seed, replay the recorded actions, and compare each generated state ID, reward, lives value and next-frame SHA-256.

A divergence produces the first mismatch and exits nonzero. It is evidence; the verifier does not tune or rewrite history.

## One-player outcome

A one-player comparison is deliberately called an **evaluation winner**, not a literal Space Invaders win.

Example:

    python scripts/determine_game_outcome_v1.py 1p --left-run 3 --right-run 8

The comparison requires both trace/MMR verifications, the same seed, the same step budget and matching ALE/Gymnasium/NumPy runtime versions. The frozen predicate is higher final cumulative environment score; equal score is a tie.

The recorded summaries currently show scripted seed 3 at 325 and the local Ollama seed 3 baseline at 270, but the deterministic outcome script must verify their trace bytes/MMRs before emitting a winner.

## Two-player outcome

For an executed PettingZoo E5 2P summary:

    python scripts/determine_game_outcome_v1.py 2p --summary results/vita01/e5/E5_2P_M2.json --seed 3

The verifier checks the gzip SHA-256, recomputes every episode leaf and MMR, then derives the match result from the two final environment score accumulators:

- score(first_0) > score(second_0): first_0 wins
- score(first_0) < score(second_0): second_0 wins
- equality: TIE

The winning seat's frozen arm label is reported. This is a deterministic **match winner**, not a semantic claim that the model completed the entire Space Invaders game.

If the ROM gate blocked the 2P lane or no verified trace exists, the outcome is NOT_ESTABLISHED.

## Literal game completion

No current predicate treats positive score, termination, lives lost or prose/video interpretation as a literal game win. A separate environment-derived completion or wave-clear predicate must be preregistered before such a claim is made.

## Tenki roles

Tenki Code Reviewer should review these scripts for:
- hash construction and trace reconstruction;
- first-divergence preservation;
- no mutation/rewrite path;
- winner predicate correctness;
- secret handling;
- exact Mitosis universal-ID requirements;
- no silent PASS upgrades.

A later Tenki clean sandbox should execute the same scripts at an exact source commit. Code review and execution verification remain separate FCOs.

## Mitosis boundary

Mitosis universal IDs are addresses. Exact query/get identity can establish persistence/retrieval. The FCO canonical hash remains evidence identity; Merkle/MMR roots remain checkpoint commitments.

Portable/load-bearing memory remains NOT_ESTABLISHED until a Tenki verification result is written to Mitosis, exactly retrieved, admitted by Vithia, and causally consumed by a subsequent DecisionFCO.
