#!/usr/bin/env python3
"""v2 of verify_competition_lineage.py (immutable atom of UFA-JEV-COMP-BP-0012).
Fixes a real finding: the original only checked that identity fields
(lineage_id, branch, parent_root, breakpoint_id, breakpoint_root) were
*present* in each breakpoint document, never that they *equal* the ledger
entry's own recorded values or form the expected parent chain. Since
qualified_breakpoint.py's create() merged a caller-supplied body dict without
guarding identity keys, a call could have silently diverged the document from
the ledger while both still hashed internally-consistently, and this verifier
would still report PASS. scripts/qualified_breakpoint.py itself is not a
protected atom and has been fixed directly to reject such bodies going
forward; this v2 verifier additionally re-checks doc-vs-ledger equality and
the parent-root chain for every existing entry.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file
LP = ROOT / "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"


def main():
    j = json.loads(LP.read_text())
    errors = []
    leaves = []
    assert j["lineage_id"] == "UFA-JEV-COMP"
    if j.get("predecessor_roots_are_mmr_leaves") is not False:
        errors.append("PREDECESSOR_MMR_CONFLATION")
    for i, e in enumerate(j["entries"]):
        if e["seq"] != i:
            errors.append(f"SEQ:{e['bp_id']}")
        p = ROOT / e["bp_file"]
        doc = json.loads(p.read_text())
        fsha, _ = sha256_file(p)
        if fsha != e["bp_file_sha256"]:
            errors.append(f"BP_FILE_SHA:{e['bp_id']}")
        for k in ("lineage_id", "branch", "parent_root", "breakpoint_id", "breakpoint_root"):
            if k not in doc:
                errors.append(f"OCCURRENCE_FIELD:{e['bp_id']}:{k}")
        if doc.get("lineage_id") != j["lineage_id"]:
            errors.append(f"LINEAGE_ID_MISMATCH:{e['bp_id']}")
        if doc.get("breakpoint_id") != e["bp_id"]:
            errors.append(f"BREAKPOINT_ID_MISMATCH:{e['bp_id']}")
        if doc.get("branch") != e.get("branch"):
            errors.append(f"BRANCH_MISMATCH:{e['bp_id']}")
        if doc.get("parent_root") != e.get("parent_root"):
            errors.append(f"PARENT_ROOT_MISMATCH:{e['bp_id']}")
        if leaves and doc.get("parent_root") != mmr_root(leaves)[0]:
            errors.append(f"PARENT_CHAIN_BROKEN:{e['bp_id']}")
        groups = {}
        for a in doc["atoms"]:
            ap = ROOT / a["path"]
            sha, n = sha256_file(ap)
            if sha != a["sha256"] or n != a["bytes"]:
                errors.append(f"ATOM_CHANGED:{a['path']}")
            lf = leaf(a["path"], a["bytes"], a["sha256"])
            if lf.hex() != a["fmo_leaf"]:
                errors.append(f"LEAF:{a['path']}")
            groups.setdefault(a["group"], []).append((a["path"], lf))
        root, _ = fmo_root(groups)
        if root != e["bp_root"] or root != doc["bp_root"]:
            errors.append(f"BP_ROOT:{e['bp_id']}")
        if doc.get("breakpoint_root") != root:
            errors.append(f"BREAKPOINT_ROOT_MISMATCH:{e['bp_id']}")
        lf = mmr_leaf(i, e["bp_id"], root, fsha)
        leaves.append(lf)
        if lf.hex() != e["mmr_leaf"]:
            errors.append(f"MMR_LEAF:{e['bp_id']}")
        after, _ = mmr_root(leaves)
        if after != e["mmr_root_after"]:
            errors.append(f"MMR_ROOT_AFTER:{e['bp_id']}")
    final, _ = mmr_root(leaves)
    print("COMP_LINEAGE_ID=" + j["lineage_id"])
    print("COMP_MMR_SIZE=" + str(len(leaves)))
    print("COMP_MMR_ROOT=" + final)
    print("COMP_BREAKPOINT_VERIFY=" + ("PASS" if not errors else "FAIL"))
    for x in errors:
        print(x)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
