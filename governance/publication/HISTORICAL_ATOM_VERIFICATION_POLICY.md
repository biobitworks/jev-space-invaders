# Historical atom verification policy

Publication breakpoints commit path, exact byte length, SHA-256, and FMO leaf identity.

A successor publication state may change a working-tree path. This does not rewrite the bytes committed by an earlier breakpoint because Git preserves the predecessor snapshot.

Verification order:
1. verify the current working-tree file if it still matches the committed byte length and SHA-256;
2. otherwise recover the exact file bytes from the Git commit that first introduced the breakpoint file;
3. require those historical bytes to match the atom's committed length and SHA-256;
4. fail if neither current nor historical bytes match.

The breakpoint JSON itself and the ordered publication MMR ledger remain strict current-tree immutable governance artifacts.

Historical Git recovery establishes custody of predecessor bytes, not truth or correctness.
