#!/usr/bin/env python3
"""Verify VITHIA-HACKDAY-BP-0001 Merkle construction.

This verifies the breakpoint manifest's canonical leaf hashing and Merkle root.
It does not prove scientific truth, causality, experiment execution, Git object
availability, MMR commitment, or signatures.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


LEAF_PREFIX = b"FCO_LEAF_V1\0"
NODE_PREFIX = b"FCO_NODE_V1\0"


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(payload: object) -> bytes:
    return sha256(LEAF_PREFIX + canonical_json_bytes(payload))


def merkle_root(digests: list[bytes]) -> bytes:
    if not digests:
        raise ValueError("empty leaf set")
    level = list(digests)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            sha256(NODE_PREFIX + level[i] + level[i + 1])
            for i in range(0, len(level), 2)
        ]
    return level[0]


def main() -> int:
    path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "publication/breakpoints/VITHIA-HACKDAY-BP-0001.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))

    observed = []
    ok = True

    for leaf in data["leaves"]:
        got = leaf_hash(leaf["payload"]).hex()
        expected = leaf["leaf_sha256"]
        state = "PASS" if got == expected else "FAIL"
        print(f'LEAF[{leaf["index"]}]={state} expected={expected} got={got}')
        if got != expected:
            ok = False
        observed.append(bytes.fromhex(got))

    got_root = merkle_root(observed).hex()
    expected_root = data["construction"]["merkle_root_sha256"]
    root_state = "PASS" if got_root == expected_root else "FAIL"
    print(f"MERKLE_ROOT={root_state}")
    print(f"EXPECTED_ROOT={expected_root}")
    print(f"RECOMPUTED_ROOT={got_root}")

    if data.get("mmr_state") != "NOT_CREATED":
        print("WARNING: this verifier does not verify an MMR")
    if data.get("signature_state") != "NOT_SIGNED":
        print("WARNING: this verifier does not verify signatures")

    print(f"OVERALL={'PASS' if ok and got_root == expected_root else 'FAIL'}")
    return 0 if ok and got_root == expected_root else 1


if __name__ == "__main__":
    raise SystemExit(main())
