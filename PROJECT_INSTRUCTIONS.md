# Project settings — UFA JEV Space Invaders

## Objective

Enter and compete in the UFA JEV Bake-Off Space Invaders arena. Build a reproducible JEV decision agent and a comparable LLM baseline, maximize measured performance/speed/cost, and preserve every run.

## Hard competition rules

1. Read the current UFA arena llms.txt before changing submission assumptions.
2. Never invent registration identity, team, sponsor use, access, attendance, repo, or demo-video fields.
3. JEV must make the core decisions for the selected track.
4. Use fixed seeds and run at least five JEV games and five baseline games.
5. After every game, append the actual run to root results.json, commit it, and push before the next game.
6. Failed and short games are preserved; never delete a bad run to improve the story.
7. Record observed values only: served model id, score, steps/frames, model calls, tokens, latency, errors/retries, confidence, cost, wall time.
8. Public repo must run from README; no hard-coded scores.
9. Resubmit the entry with the same email whenever repo or demo-video URL changes.
10. Only report ENTERED when the UFA server returns ok=true.

## Scientific/governance state

PROPOSED is not IMPLEMENTED. IMPLEMENTED is not EXECUTED. EXECUTED is not OBSERVED. OBSERVED is not SUPPORTED.

Preserve FAILED, NULL, NEGATIVE, DEFERRED, NOT_TESTED, UNKNOWN, and NOT_COMPUTED. Hashes establish identity only. Merkle/MMR and signatures are not claimed unless actually computed and verified.

## Winning optimization order

Performance > speed/cost > first-15-second demo clarity > originality > sponsor stack, while satisfying all rules.

Default engineering path: deterministic harness first; JEV pilot second; identical System One adapter baseline third; sponsor integration only if genuinely load-bearing and measured.
