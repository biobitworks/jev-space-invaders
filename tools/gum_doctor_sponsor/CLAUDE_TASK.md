# Claude task: final sponsor + video completion

You are the sole repository writer for this execution cycle.

Start with:

```bash
bash tools/gum_doctor_sponsor/run.sh
```

Read the resulting sanitized status. Never print, cat, grep, summarize, or
commit `.private/sponsor-proof/.env`.

## Goal

Finish the smallest truthful submission path:

```
existing ReplaySeedFCO
→ Mitosis persistent memory
→ Tenki clean-room verification
→ VerificationFCO
→ Mitosis writeback/retrieval
→ final video assets
→ tests/scans
→ commit/push
```

Do not rebuild orchestration.

## Evidence boundaries

Qualified predecessor `UFA-JEV-COMP-BP-0017` is immutable.

Existing bounded local OpenJEV evidence remains engineering evidence:
- raw p50 5626.834 ms
- Vithia L1 p50 4725.3426 ms
- delta p50 -901.4914 ms
- raw p95 6176.3331 ms
- Vithia p95 7057.1172 ms
- score delta 0
- scope 3 seeds × 3 steps

Existing ReplaySeed root:
`85f01e8a1c8b613ac99a3d1b2476c7f3a8dc083540c5ab413893858656030a5b`

Existing replay claims:
- REPLAY_FROM_START=PASS
- STEP_HASH_EQUALITY=PASS
- FINAL_MMR_EQUALITY=PASS

Never relabel OpenJEV as hosted TypeSafe JEV.

## Mitosis

If a Mitosis credential is present, execute the minimum real write + retrieve
cycle for a compact ReplaySeed summary. Preserve the returned universal ID and
a sanitized receipt. Mitosis is outside the per-action latency hot path.

## Tenki

If a Tenki credential/token is present, create one clean sandbox, clone the
public repository at the exact source commit, and verify the committed
ReplaySeed/content/action/step/MMR/replay evidence. Do not rerun OpenJEV
inference merely for sponsor verification. Produce a sanitized
TenkiVerificationFCO/receipt.

## Closed sponsor loop

Only if Tenki verification succeeds:
1. write the verification reference back to Mitosis;
2. retrieve it;
3. then and only then set
   `PORTABLE_AGENT_MEMORY_LOAD_BEARING=PASS`.

Mitosis PASS by itself is not enough.

## TypeSafe JEV

If `TYPESAFE_API_KEY` is present, run the smallest real hosted-JEV smoke
through the existing fail-closed JEV backend and record it separately.
Do not substitute another provider.

## Ollarma/local workers

Ollarma/Qwen/Liquid/OpenJEV may be used for bounded review, code checking, or
existing local execution. They do not become additional repository writers.

## Video

Prepare the real evidence middle section for the human face/voice recording:
1. result: 5626.8 ms → 4725.3 ms, -901.5 ms median, clearly labeled bounded
   local OpenJEV, 3 seeds × 3 steps;
2. committed ALE frames with actual action/context/MMR telemetry;
3. ReplaySeed proof;
4. actual sponsor receipts only if executed;
5. judge BYO TypeSafe-key command.

Do not fabricate gameplay or sponsor execution.

## Verification and durability

Before claiming completion:
- run relevant pytest/tests;
- ReplaySeed verifier;
- qualified lineage verifier;
- git diff --check;
- secret scan;
- private-IP scan.

If full pytest fails for an unrelated import error, report that exact state;
do not call the full suite PASS.

Commit and push each completed public-safe milestone promptly. Never force
push. Verify remote refs after pushing.

## Final return

Return only:

```
HEAD=
ORIGIN_HEAD=
ORIGIN_PARITY=
SPONSOR_ENV=
MI_API_KEY=
TENKI_API_KEY=
TYPESAFE_API_KEY=
ANTHROPIC_API_KEY=
OLLARMA=
OLLAMA_MODELS=
OPENJEV=
MITOSIS=
MITOSIS_UNIVERSAL_ID=
MITOSIS_QUERY=
TENKI=
TENKI_SESSION_ID=
TENKI_REPLAY_VERIFY=
TENKI_RECEIPT_HASH=
MITOSIS_VERIFY_WRITEBACK=
MITOSIS_RETRIEVE_TENKI_PROOF=
PORTABLE_AGENT_MEMORY_LOAD_BEARING=
REAL_JEV=
VIDEO_ASSETS=
VIDEO_ASSEMBLY_READY=
TESTS=
SECRET_SCAN=
PRIVATE_IP_SCAN=
COMMIT=
PUSH=
BLOCKED=
NEXT_ACTION=
```
