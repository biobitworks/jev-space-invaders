#!/usr/bin/env python3
"""Recompute every breakpoint root and the MMR from scratch. Trusts no stored root."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file  # noqa: E402

LEDGER = ROOT / "governance" / "MMR_LEDGER.json"


def main() -> int:
    if not LEDGER.exists():
        print("BREAKPOINT_VERIFY=FAIL\nNO_LEDGER")
        return 2
    ledger = json.loads(LEDGER.read_text())
    errors, skipped, leaves = [], [], []
    for i, e in enumerate(ledger["entries"]):
        f = ROOT / e["bp_file"]
        if e["seq"] != i:
            errors.append(f"SEQ:{e['bp_id']}")
        if not f.exists():
            errors.append(f"MISSING_BP_FILE:{e['bp_file']}")
            continue
        fsha, n = sha256_file(f)
        if fsha != e["bp_file_sha256"]:
            errors.append(f"BP_FILE_SHA:{e['bp_id']}")
        if e["root_kind"] == "LEGACY_SINGLE_ATOM":
            root, _ = fmo_root({"legacy": [(e["bp_file"], leaf(e["bp_file"], n, fsha))]})
        else:
            doc = json.loads(f.read_text())
            groups: dict[str, list] = {}
            for a in doc["atoms"]:
                p = ROOT / a["path"]
                if not p.exists():
                    if a["location"] == "private":
                        skipped.append(a["path"])
                    else:
                        errors.append(f"MISSING_ATOM:{a['path']}")
                else:
                    sha, nb = sha256_file(p)
                    if sha != a["sha256"] or nb != a["bytes"]:
                        errors.append(f"ATOM_CHANGED:{a['path']}")
                lf = leaf(a["path"], a["bytes"], a["sha256"]).hex()
                if lf != a["fmo_leaf"]:
                    errors.append(f"LEAF:{a['path']}")
                groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(lf)))
            root, _ = fmo_root(groups)
            if root != doc["bp_root"]:
                errors.append(f"BP_ROOT_IN_FILE:{e['bp_id']}")
        if root != e["bp_root"]:
            errors.append(f"BP_ROOT:{e['bp_id']}")
        lf = mmr_leaf(i, e["bp_id"], root, fsha)
        if lf.hex() != e["mmr_leaf"]:
            errors.append(f"MMR_LEAF:{e['bp_id']}")
        leaves.append(lf)
        after, _ = mmr_root(leaves)
        if after != e["mmr_root_after"]:
            errors.append(f"MMR_ROOT_AFTER:{e['bp_id']}")
        print(f"{e['bp_id']}  {e['root_kind']:<28} root={root[:16]}…  mmr={after[:16]}…")
    final, _ = mmr_root(leaves)
    print(f"MMR_SIZE={len(leaves)}")
    print(f"MMR_ROOT={final}")
    if skipped:
        print(f"PRIVATE_ATOMS_NOT_PRESENT={len(skipped)} (committed by hash; not re-read)")
    print("BREAKPOINT_VERIFY=" + ("PASS" if not errors else "FAIL"))
    for x in errors:
        print(x)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
