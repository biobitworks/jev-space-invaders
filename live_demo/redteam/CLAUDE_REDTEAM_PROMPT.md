# RED_TEAM_PER_SEAT_DECIDER_AND_PREPROCESSOR_E2E_V02

Review the exact committed HEAD supplied by the Ollarma watcher. Treat the
repository as the source of truth and do not modify protected publication
branches or historical competition atoms.

Focus on P0 correctness:

1. `PlayerSeatConfig` is the only 1P/2P controller configuration. Each seat
   has an independent preprocessor and decider.
2. Vithia preprocessing emits context only and never chooses a counted action.
3. System-One is a stable interface with `OPENJEV_LOCAL` and reserved
   `JEV_API_REMOTE` backends. Qwen and Liquid are alternate deciders.
4. Provider status separates current runtime from historical evidence. Do not
   promote Tenki or Mitosis from receipts alone; Mitosis may be context-only.
5. Blocking preprocessing/inference occurs outside the control lock. Pause,
   stop, reset, preprocessor changes, and decider changes invalidate old
   generations. No stale result may call `env.step`.
6. 1P performs one decision and one ALE transition. 2P performs two seat
   decisions and exactly one PettingZoo joint transition.
7. Headless seat configuration works without a browser.

Run the focused tests and inspect the live acceptance receipt. Report
`P0_FINDINGS`, `P1_FINDINGS`, `P2_FINDINGS`, exact file/line evidence, tests
run, and whether the result is `REDTEAM_CLEAR`. If a P0 finding exists, do not
silently patch it: emit a repair request against the exact tested HEAD.
