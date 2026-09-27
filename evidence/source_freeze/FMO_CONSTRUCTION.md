# Fractal Merkle Object V1 — source freeze

Root kind: `FRACTAL_MERKLE_OBJECT_V1_SOURCE_FREEZE`

Root: `28c9beac8c617df2c8409b50d45ee6240408455c53db5b845261fb4005171a81`

The root commits to exact downloaded bytes through path-bound leaves. It establishes identity/custody only, not truth, safety, security, or license sufficiency.

1. For each cached file, compute raw SHA-256.
2. Sort files lexicographically by relative path inside each top-level group.
3. Leaf = `SHA256("FMO_LEAF_V1\0" || path || "\0" || byte_count || "\0" || raw_sha256_hex)`.
4. Pair leaves using `SHA256("FMO_NODE_V1\0" || left_digest || "\0" || right_digest)`; duplicate the last digest at odd levels.
5. Bind each group root with `SHA256("FMO_GROUP_V1\0" || group_name || "\0" || group_root_hex)`.
6. Sort group commitments by group name and Merkle-combine them with the same node rule.

`MMR=NOT_COMPUTED`. `SIGNATURE=NOT_SIGNED`.
