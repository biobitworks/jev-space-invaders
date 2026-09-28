# Submission red-team report

Adversarial review of the UFA-JEV-COMP qualified competition lineage
(`competition/qualified-lineage-v01` + `competition/final-integration-v01`),
performed as a skeptical judge trying to falsify every claim. Full per-claim
evidence and falsification attempts are in `CLAIM_EVIDENCE_MATRIX.json`
alongside this file. Summary verdicts:

| Claim | Verdict |
|---|---|
| JEV used | NOT_SUPPORTED |
| System-One official baseline used | NOT_SUPPORTED |
| OpenJEV comparator valid | NOT_SUPPORTED |
| Vithia trained | NOT_SUPPORTED |
| Mitosis used | PARTIAL |
| Tenki used | SUPPORTED |
| 2P ready | NOT_SUPPORTED |
| Real-time | NOT_SUPPORTED |
| Cost advantage | NOT_TESTED |
| Reproducible | PARTIAL |
| MMR proves correctness | NOT_SUPPORTED (never claimed) |
| Sponsor integration load-bearing | PARTIAL |

## What independently checked out well

- **Tenki code review**: independently re-verified against the live GitHub API
  (`gh api repos/biobitworks/jev-space-invaders/pulls/1/reviews`), not just
  trusted from the repo's own receipt. Exact match: review id
  `PRR_kwDOUuZx2c8AAAABPbs_4g`, `tenki-reviewer[bot]`, `APPROVED`,
  `2026-09-27T14:18:42Z`.
- **Tenki sandbox execution**: the imported run's `runtime.platform` is
  `Linux-6.18.29-x86_64-with-glibc2.39` — this session's own host is macOS
  arm64, so a Linux platform fingerprint in the trace is strong independent
  evidence the run genuinely executed on a remote machine, not fabricated
  locally.
- **Mitosis retrieval was actually consumed**: the seed Mitosis returned
  (3) is the seed the Tenki run actually used, not a coincidence — both
  records cross-reference the same `universal_id`.
- **OpenJEV capability-mismatch claim**: independently re-derived by reading
  `shim_mlx.py` over SSH and attempting (and correctly declining to force
  past) the `READOUT_TARGETED=1` gate myself, before this receipt existed.
- **The claim_ceiling discipline is real, not decorative**: every breakpoint
  in every branch audited this session carries
  `"hashes do not establish correctness"`, and no evidence file anywhere
  overclaims what a Merkle root proves.
- **The legacy BP-0010 verifier failure is genuinely a pre-existing defect**,
  not something anyone tried to hide: it surfaced honestly and is documented.

## New findings from this pass

1. **Unbounded sponsor cost risk.** `TENKI_SESSION_CREATE_RECEIPT.json`
   records only `id, name, state, sticky` — no CPU/memory/disk resource
   ceiling and no auto-teardown timer are recorded anywhere. The session has
   been `sticky=true` and held open (`teardown_state: HELD_NO_TERMINATE_CALL`)
   through several breakpoints already. If the demo-video step stalls, this
   session could remain billing indefinitely with no recorded guard. This is
   a real gap against section 20's "unbounded sponsor costs" check, not
   hypothetical — the receipts show it already happening.
2. **Absolute machine paths throughout provenance records** (`/Volumes/
   magicBLACKbox/...`, `/Users/byron/...`). These are legitimate — they
   document exactly which machine something ran on — but they mean a fresh
   clone on a different machine cannot literally re-run the OpenJEV or Liquid
   lanes without those exact paths existing. This is the concrete basis for
   classifying "reproducible" as PARTIAL rather than SUPPORTED.
3. **Branch incoherence remains unresolved.** At least 4 branches diverge
   from a common point; two of them (`openjev/kaggle-systemone-v01`,
   `magicstudio/sponsor-ollama-adapter-20260928`) delete evidence this
   lineage's own breakpoints cite as atoms, and one of them edits protected
   breakpoint atoms directly (`src/deciders.py`, `scripts/run_games.py`). A
   judge who checks out the wrong branch would see a different, conflicting
   story. See `evidence/competition/governance/CONCURRENT_WRITER_COLLISION_RECEIPT.json`.
4. **Error handling is intentional, not swallowed.** `OllamaBaselineDecider`
   and `LiquidOllamaDecider` both catch broad exceptions during response
   parsing and fall back to holding the previous action, but every fallback
   is counted in `fallback_actions` (0 across all 5 executed M3 runs) —
   nothing is silently hidden.
5. **Mitosis's load-bearing claim is thinner than it first appears.** The
   mechanism genuinely executed (write → retrieve → consumed by a real run),
   but the retrieved value only selected which fixed seed to run — a fairly
   low bar for "load-bearing." No ablation (with vs. without Mitosis) exists
   to show the retrieval changed any outcome that mattered. This is why the
   claim is PARTIAL, not SUPPORTED, in the matrix.

## What must not be claimed in the demo or entry, given current evidence

- Do not say JEV, official System-One, or matched OpenJEV executed.
- Do not present the local-Ollama baseline as real-time capable (RTF ≈ 0.11).
- Do not present a cost comparison of any kind — no comparable hosted lane
  has ever executed.
- Do not present 2P gameplay, live or recorded.
- Do not claim "sponsor integration" without the PARTIAL/SUPPORTED
  distinction above (Tenki: yes; Mitosis: narrowly, not ablation-proven).
- Do not present a Merkle root or MMR verification result as evidence of
  scientific correctness.

## Not covered by this pass

- Full static/lint audit and dependency audit (section 20) were not run in
  this pass beyond `pytest`, `secret_scan.py`, and manual review of the
  specific risk categories listed in section 20. No linter is configured in
  this repo as far as this session found.
- Test isolation / test leakage was not independently deep-audited.
