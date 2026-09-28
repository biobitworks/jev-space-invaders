# D0-D9 post-confirmatory secondary statistical analysis

Status: POST_CONFIRMATORY_SECONDARY_ANALYSIS_PREREGISTRATION.

This successor does not alter E0-E4A hypotheses, terminal states, datasets, preregistrations, or historical breakpoints. It derives uncertainty/effect summaries from already-frozen E1-E3 outputs.

Fixed analyses:
- E1/H1d: Wilson 95% interval for final rank-1 fraction; difference from preregistered 0.90 threshold.
- E1/H1e and H1e_v2: Cliff's delta and deterministic bootstrap 95% interval for the median difference (missing_row - exact), preserving FAIL_TO_REJECT_H0 regardless of secondary effect estimates.
- E2/H2d: matched (scene,t) accuracy difference CORRECT_HISTORY - SHUFFLED_HISTORY, and matched unknown-rate difference NO_HISTORY - CORRECT_HISTORY; deterministic bootstrap 95% intervals.
- E3/H3b: paired max-EIG vs random actual-gain mean difference, median difference, paired Cohen dz, deterministic bootstrap 95% interval.
- E3/H3c: signed actual-gain minus predicted-EIG mean difference and absolute mean-gap bootstrap interval.
- E3: ABSTAIN_SIZE_LIMIT state fraction and exact counts.

Bootstrap:
- RNG: NumPy default_rng
- seed: 20260927
- resamples: 10000
- percentile interval: [2.5%, 97.5%]

Claim mutation: NO.
These are secondary descriptive/inferential summaries. Existing confirmatory claim states remain immutable.
