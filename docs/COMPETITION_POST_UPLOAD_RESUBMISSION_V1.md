# Competition post-upload resubmission procedure V1

State: PREPARED_NOT_EXECUTED.

This procedure begins only after a real public or competition-accepted demo URL exists.

## Evidence boundary

The live collection route https://mitosislabs.ai/api/ufa/jev/entries was probed read-only on 2026-09-28. OPTIONS returned 204 with Access-Control-Allow-Methods: POST, OPTIONS; GET returned 405. The guessed per-entry route /entries/{entry_id} returned 404 and explicitly said it is not an API endpoint.

Therefore the repository currently proves that the collection accepts POST. It does not independently prove whether a later POST updates the existing entry, creates another submission, or increments a submission history. Do not infer upsert semantics from submission_count.

The frozen competition plan nevertheless requires a final resubmission after the demo URL exists, with a successful server response whose missing_for_judging is empty. Treat that as the intended competition workflow, not as proof of server identity semantics.

## Human prerequisites

1. Record the demo using evidence/competition/demo/DEMO_SCRIPT.md.
2. Review it using evidence/competition/demo/DEMO_CHECKLIST.md.
3. Upload it using a competition-accepted public or accessible host.
4. Obtain the actual HTTPS video URL.
5. Recover the original private entry.local.json from the operator secret boundary. It is intentionally git-ignored and is not present in the canonical worktree.

Do not reconstruct private contact fields from memory or repository guesses.

## Prepare the private payload

Run:

    python scripts/prepare_entry_resubmission_v1.py \
      --source entry.local.json \
      --output entry.resubmit.local.json \
      --demo-video-url "https://ACTUAL-VIDEO-URL"

The script is intentionally network-free. It fails closed unless the expected original schema exists. It changes only the final public competition state needed by the current evidence:

- build.repo_url -> canonical public repository URL
- build.demo_video_url -> actual supplied HTTPS URL
- sponsors.mitosis -> false
- sponsors.tenki -> false
- sponsors.how -> truthful non-execution wording
- needs_jev_access -> true

All other fields are preserved from the private source payload.

entry.resubmit.local.json must remain private and git-ignored.

## Before any network submission

Require all of:

    git fetch origin
    git status --short --branch
    python scripts/verify_competition_lineage.py
    python scripts/validate_results.py

And verify:

- canonical branch is competition/qualified-lineage-v01;
- local HEAD equals origin;
- worktree is clean;
- no competing writer has advanced the branch;
- qualified verification is PASS;
- results validation is PASS;
- demo URL resolves as intended;
- no credentials or private fields will be committed;
- Mitosis and Tenki remain false unless new governed load-bearing execution receipts exist.

## Submission gate

Do not POST merely because this procedure exists.

Before network mutation, establish the accepted resubmission path from an organizer-facing UI, organizer instruction, or a verified API contract. The current public collection route exposes POST but does not expose a verified per-entry update route.

After an authorized resubmission, preserve the complete server response in a new immutable successor receipt. The success gate is:

- HTTP success;
- response ok == true;
- missing_for_judging == [];
- actual demo URL represented by the submitted payload;
- sponsor fields match governed execution truth;
- public repository points to the intended final commit.

Do not modify FINAL_ENTRY_UPDATE_V2.json. Create a new successor.

## Claim ceiling

This procedure proves only that a fail-closed resubmission payload can be prepared locally. It does not prove that a final entry update has been submitted or accepted.
