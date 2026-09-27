"""FMO V1 hashing and a Merkle Mountain Range over breakpoint roots.

Leaf/node rules are byte-identical to scripts/verify_source_freeze.py and
evidence/source_freeze/FMO_CONSTRUCTION.md. MMR rules are defined in
docs/BREAKPOINT_PROTOCOL.md. Hashes establish identity, not correctness.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def hp(prefix: str, *parts) -> bytes:
    payload = prefix.encode() + b"\0" + b"\0".join(
        p if isinstance(p, bytes) else str(p).encode() for p in parts
    )
    return hashlib.sha256(payload).digest()


def sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def leaf(path: str, nbytes: int, sha_hex: str) -> bytes:
    return hp("FMO_LEAF_V1", path, nbytes, sha_hex)


def merkle(nodes: list[bytes]) -> bytes:
    if not nodes:
        return hashlib.sha256(b"FMO_EMPTY_V1").digest()
    nodes = list(nodes)
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [hp("FMO_NODE_V1", nodes[i], nodes[i + 1]) for i in range(0, len(nodes), 2)]
    return nodes[0]


def fmo_root(groups: dict[str, list[tuple[str, bytes]]]) -> tuple[str, dict[str, str]]:
    """groups: name -> [(path, leaf_digest)]. Returns (root_hex, {group: group_root_hex})."""
    group_roots: dict[str, str] = {}
    commits = []
    for g in sorted(groups):
        gr = merkle([d for _, d in sorted(groups[g])]).hex()
        group_roots[g] = gr
        commits.append(hp("FMO_GROUP_V1", g, gr))
    return merkle(commits).hex(), group_roots


def mmr_leaf(seq: int, bp_id: str, bp_root_hex: str, bp_file_sha_hex: str) -> bytes:
    return hp("MMR_LEAF_V1", seq, bp_id, bp_root_hex, bp_file_sha_hex)


def mmr_root(leaves: list[bytes]) -> tuple[str, list[str]]:
    """Append leaves left to right, merging equal-height peaks; bag peaks right to left."""
    peaks: list[tuple[int, bytes]] = []
    for lf in leaves:
        h, d = 0, lf
        while peaks and peaks[-1][0] == h:
            _, left = peaks.pop()
            d = hp("MMR_NODE_V1", left, d)
            h += 1
        peaks.append((h, d))
    if not peaks:
        return hashlib.sha256(b"MMR_EMPTY_V1").digest().hex(), []
    acc = peaks[-1][1]
    for _, d in reversed(peaks[:-1]):
        acc = hp("MMR_BAG_V1", d, acc)
    return acc.hex(), [d.hex() for _, d in peaks]
