# Pre-execution red-team report (Claude -> Codex handoff)

Scoped to the preparation work done in this pass: PettingZoo dependency prep,
2P code review, frame-custody pipeline, and TUI. See
`evidence/competition/redteam/SUBMISSION_RED_TEAM_REPORT.md` and
`CLAIM_EVIDENCE_MATRIX.json` for the broader competition-claim audit; this file
covers only what changed in this pass.

| Check | Result |
|---|---|
| Protected-atom mutation | NONE. `requirements-2p.txt` is a new file; `requirements.txt` untouched. `src/frame_custody.py`, `scripts/record_governed_playthrough.py`, `scripts/verify_playthrough_custody.py`, `scripts/render_playthrough_video.py`, `tools/playthrough_tui.py` are all new files. `FCO_REGISTRY.json`/`FCG_EDGES.json` were appended to, not rewritten (existing entries byte-identical, diff-checked). |
| Branch collision | None newly introduced; existing collisions already documented in `evidence/competition/governance/CONCURRENT_WRITER_COLLISION_RECEIPT.json` (UFA-JEV-COMP-BP-0009), unchanged this pass. |
| Secret leakage | `secret_scan.py` PASS (444 files). Private Ed25519 key confirmed gitignored (`git check-ignore` verified) and never printed. |
| Test leakage | Not independently deep-audited this pass (same caveat as the earlier red-team report). |
| Hard-coded paths | `src/frame_custody.py` and the record/verify/render scripts are all `ROOT`-relative, no hard-coded machine paths. The PettingZoo venv itself lives at a machine-specific path on magicSTUDIObox (`/Volumes/magicBLACKbox/...`), documented as such in `TWO_PLAYER_DEPENDENCY_MANIFEST.json` - same caveat already flagged for OpenJEV/Liquid runtime paths. |
| Fake 2P | None. `TWO_PLAYER_CODE_READINESS_RECEIPT.json` explicitly states `EXECUTION_NOT_TESTED`; no 2P episode was ever run; ROM gate remains `BLOCKED`. |
| Fake live capture | None. The only capture performed is a 24-frame `SETUP_SMOKE_NON_SUBMISSION_NON_EXPERIMENTAL` playthrough, labeled as such everywhere it appears (FCO registry, construction/verification receipts). No video was rendered - `render_playthrough_video.py` was written but not executed (operator explicitly stopped that step). |
| Browser UI fed into model | N/A this pass - no browser dashboard was built (deferred; see handoff `KNOWN_BLOCKERS`). The TUI (`tools/playthrough_tui.py`) is documented as replay-only, operator-facing, never model input. |
| Fake probabilities | None introduced. |
| Unverified signatures | None. Every frame occurrence's Ed25519 signature is independently re-verified in `verify_playthrough_custody.py` by loading the embedded public key and calling `verify()` before the frame counts as reconstructed. |
| Unverified MMR | None. `PLAYTHROUGH_MMR_VERIFICATION_RECEIPT.json` records `PLAYTHROUGH_VERIFY=PASS` with the recomputed root matching the recorded root exactly, for all 24 frames. |
| Sponsor overclaim | None introduced this pass; unchanged from the earlier audit (Mitosis PARTIAL, Tenki SUPPORTED). |
| Video assembled from non-canonical frames | N/A - no video exists yet. |

## New finding this pass

The operator explicitly declined a proposal to erasure-code the public key and
distribute shards across pixel regions of custody frames. That was the right
call: it would have written synthetic data into the frames whose whole purpose
is to hash the *unmodified* ALE output, contaminating `RAW_RGB_CONTENT_SHA256`.
The public key is published in plaintext instead (`FRAME_CUSTODY_PUBLIC_KEY.pem`)
and referenced by fingerprint - no pixel data is altered anywhere in this
pipeline. Codex should not reintroduce pixel-level data embedding without
re-deriving a real reason for it; "the key needs redundancy" does not apply
to a public key already committed to the repo.
