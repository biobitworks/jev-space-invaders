# Breakpoint protocol (atom roots + MMR)

A breakpoint is an append-only JSON in `governance/breakpoints/NNNN-slug.json`.

## Atoms and breakpoint root

Each breakpoint lists its atoms (FCOs): `path, kind, group, bytes, sha256, location, fmo_leaf`.

- `fmo_leaf = SHA256("FMO_LEAF_V1\0" || path || "\0" || bytes || "\0" || sha256_hex)`
- Atoms are grouped by `group`; each group is Merkle-combined with
  `SHA256("FMO_NODE_V1\0" || left || "\0" || right)`, duplicating the last digest at odd levels.
- Group roots are bound with `SHA256("FMO_GROUP_V1\0" || group || "\0" || group_root_hex)`, sorted by
  name, and Merkle-combined into `bp_root`.

These are the same rules as `evidence/source_freeze/FMO_CONSTRUCTION.md`.

A breakpoint JSON never contains its own MMR position (that would be circular).

## MMR ledger

`governance/MMR_LEDGER.json` appends one leaf per breakpoint, in order:

`mmr_leaf = SHA256("MMR_LEAF_V1\0" || seq || "\0" || bp_id || "\0" || bp_root_hex || "\0" || bp_file_sha256_hex)`

This binds both the atom root and the exact bytes of the breakpoint file.

- **Peaks:** leaves are appended left to right. Two peaks of equal height merge as
  `SHA256("MMR_NODE_V1\0" || left || "\0" || right)`.
- **Root:** the peaks are bagged right to left, `acc = SHA256("MMR_BAG_V1\0" || peak || "\0" || acc)`.

**Breakpoints without atom roots** (BP-0001..0008, or any written by another tool) enter the MMR as `LEGACY_SINGLE_ATOM`, in file order, when the next atom-rooted breakpoint is created. For these, the breakpoint root is the FMO root over the breakpoint file itself.

**Numbering:** a new breakpoint takes the next number after the highest existing file. Its parent is that file.

## Verify

    python scripts/verify_breakpoints.py

The verifier recomputes every atom hash, breakpoint root, MMR leaf and MMR root; stored roots are not trusted. Private atoms (`artifacts/private/`) are committed by hash and are re-read only if present.

## Claim ceiling

Inclusion and identity only. A root does not establish correctness, causality, or safety. `SIGNATURE=NOT_SIGNED`.
