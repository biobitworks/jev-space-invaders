# Mitosis FCG Explorer V1

This successor projects the executed Vithia post-submission FCG into the Mitosis Cortex graph without changing the canonical evidence.

## Identity model

- **Mitosis `universal_id`**: graph address / retrieval handle.
- **FCO or receipt SHA-256**: immutable evidence identity.
- **Breakpoint FMO root**: commitment to the atoms admitted at one breakpoint.
- **MMR root**: append-only lineage checkpoint.

The graph is a projection. A Mitosis ID never replaces an FCO hash or Merkle/MMR root.

## What becomes interactive

The materializer writes one public-safe Mitosis node per admitted FCO/receipt plus one node for each of the three executed E2E breakpoints. Provenance edges are created with Mitosis `source_universal_ids`.

The existing Mitosis memory anchors are reused as external source nodes rather than duplicated.

A judge can probe by any of:

- Mitosis universal ID;
- FCO/receipt SHA-256;
- FMO leaf;
- breakpoint ID;
- breakpoint root;
- MMR root.

The probe first performs exact `cortex get` by universal ID, then asks Cortex for the node and returns Mitosis' cited graph deep-link.

## Current executed lineage

- `VITHIA-E2E-POSTSUBMISSION-BP-0001` → MMR `0428bc1bd0f7163a00b1995a5c0fbf69d7c0c2c5d04ffc5eadbb643d3cc94f5c`
- `VITHIA-E2E-POSTSUBMISSION-BP-0002` → MMR `0e39f865451949ecc08e7a90af3154d27a6043401772644f6ea75399f3e16e39`
- `VITHIA-E2E-POSTSUBMISSION-BP-0003` → MMR `d4b705060f0711b80a760300790a9f8bac3604aec28ca166c2195e9e9e5b15dc`

The graph preserves the mixed Tenki result:
- artifact reconstruction PASS;
- strict environment replay FAIL at `PNG_BYTES`;
- RGB/state/frame-root/final-MMR reproduction PASS.

## CLI

Dry-run, no credential required:

    python tools/mitosis_fcg_explorer.py materialize --dry-run

Live materialization:

    export MI_API_KEY='<interactive/private>'
    python tools/mitosis_fcg_explorer.py materialize

Probe the final root:

    python tools/mitosis_fcg_explorer.py probe       d4b705060f0711b80a760300790a9f8bac3604aec28ca166c2195e9e9e5b15dc

Probe a breakpoint:

    python tools/mitosis_fcg_explorer.py probe       VITHIA-E2E-POSTSUBMISSION-BP-0002

Verify every stored graph node against local hashes and the independently recomputed E2E MMR:

    python tools/mitosis_fcg_explorer.py verify

## Gum judge path

    bash tools/gum_mitosis_fcg_explorer.sh

Gum asks for the Mitosis key with password input and exports it only for the child process. The key is not written into Git, an FCO, Mitosis graph text, or a command-line argument.

The menu provides:
1. Materialize the graph.
2. Probe an ID/root/hash.
3. Verify graph nodes against canonical evidence.
4. Open the Mitosis cited graph URL.

## TypeSafe / JEV

TypeSafe billing is not configured and the Playground is unavailable in the current operator state. Therefore:

    TYPESAFE_BILLING=NOT_CONFIGURED
    TYPESAFE_PLAYGROUND=UNAVAILABLE
    HOSTED_JEV=NOT_EXECUTED

This does not block the graph. The current DecisionFCO uses the executed scripted policy, with the Ollama comparator separately recorded. TypeSafe/JEV remains an optional future adapter and must not be silently substituted.

## Mitosis semantics

Mitosis documents `source_universal_ids` as the provenance mechanism for linked writes. `cortex ask --json` returns a graph URL that highlights cited nodes. The explorer uses those surfaces directly.

## Materialization state

Committing this code does **not** claim the Mitosis graph has already been materialized. The live claim becomes PASS only after:

- Mitosis auth PASS;
- every node write PASS;
- exact get PASS for every returned universal ID;
- final-root probe returns the expected universal ID;
- graph index is written;
- `verify` passes.
