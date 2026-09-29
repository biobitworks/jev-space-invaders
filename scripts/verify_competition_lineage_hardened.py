#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

LP = ROOT / "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"
REQUIRED_LEDGER_FIELDS = {
    "seq",
    "bp_id",
    "bp_file",
    "bp_file_sha256",
    "bp_root",
    "branch",
    "lineage_id",
    "parent_root",
    "root_kind",
    "mmr_leaf",
    "mmr_size",
    "mmr_root_after",
}
REQUIRED_DOC_FIELDS = {
    "lineage_id",
    "branch",
    "parent_root",
    "breakpoint_id",
    "bp_root",
    "breakpoint_root",
    "root_kind",
    "atoms",
}


def verify_lineage(root: Path = ROOT, ledger_path: Path | None = None) -> tuple[dict, list[str]]:
    ledger_path = ledger_path or root / "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    errors: list[str] = []
    leaves: list[bytes] = []
    seen_seq: set[int] = set()
    seen_bp_id: set[str] = set()
    seen_bp_file: set[str] = set()

    if ledger.get("lineage_id") != "UFA-JEV-COMP":
        errors.append("LEDGER_LINEAGE_ID")
    if ledger.get("predecessor_roots_are_mmr_leaves") is not False:
        errors.append("PREDECESSOR_MMR_CONFLATION")

    for i, entry in enumerate(ledger.get("entries", [])):
        bp_label = entry.get("bp_id", f"ENTRY_{i}")
        missing = sorted(REQUIRED_LEDGER_FIELDS - set(entry))
        for field in missing:
            errors.append(f"LEDGER_FIELD_MISSING:{bp_label}:{field}")
        if missing:
            continue

        if entry["seq"] in seen_seq:
            errors.append(f"DUPLICATE_SEQ:{entry['seq']}")
        seen_seq.add(entry["seq"])
        if entry["bp_id"] in seen_bp_id:
            errors.append(f"DUPLICATE_BP_ID:{entry['bp_id']}")
        seen_bp_id.add(entry["bp_id"])
        if entry["bp_file"] in seen_bp_file:
            errors.append(f"DUPLICATE_BP_FILE:{entry['bp_file']}")
        seen_bp_file.add(entry["bp_file"])

        if entry["seq"] != i:
            errors.append(f"SEQ:{entry['bp_id']}")
        if entry["mmr_size"] != i + 1:
            errors.append(f"MMR_SIZE:{entry['bp_id']}")

        bp_path = root / entry["bp_file"]
        if not bp_path.is_file():
            errors.append(f"BP_FILE_MISSING:{entry['bp_id']}:{entry['bp_file']}")
            continue
        file_sha, _ = sha256_file(bp_path)
        if file_sha != entry["bp_file_sha256"]:
            errors.append(f"BP_FILE_SHA:{entry['bp_id']}")

        try:
            doc = json.loads(bp_path.read_text())
        except Exception as exc:
            errors.append(f"BP_FILE_JSON:{entry['bp_id']}:{exc}")
            continue

        for field in sorted(REQUIRED_DOC_FIELDS):
            if field not in doc:
                errors.append(f"OCCURRENCE_FIELD:{entry['bp_id']}:{field}")

        cross_checks = [
            ("breakpoint_id", "bp_id"),
            ("bp_root", "bp_root"),
            ("breakpoint_root", "bp_root"),
            ("branch", "branch"),
            ("lineage_id", "lineage_id"),
            ("parent_root", "parent_root"),
            ("root_kind", "root_kind"),
        ]
        for doc_field, ledger_field in cross_checks:
            if doc.get(doc_field) != entry.get(ledger_field):
                errors.append(f"CROSSCHECK:{entry['bp_id']}:{doc_field}!={ledger_field}")

        groups: dict[str, list[tuple[str, bytes]]] = {}
        for atom in doc.get("atoms", []):
            missing_atom_fields = [field for field in ("path", "group", "bytes", "sha256", "fmo_leaf") if field not in atom]
            for field in missing_atom_fields:
                errors.append(f"ATOM_FIELD:{entry['bp_id']}:{field}")
            if missing_atom_fields:
                continue
            atom_path = root / atom["path"]
            if not atom_path.is_file():
                errors.append(f"ATOM_MISSING:{atom['path']}")
                continue
            atom_sha, atom_bytes = sha256_file(atom_path)
            if atom_sha != atom["sha256"]:
                errors.append(f"ATOM_SHA:{atom['path']}")
            if atom_bytes != atom["bytes"]:
                errors.append(f"ATOM_BYTES:{atom['path']}")
            atom_leaf = leaf(atom["path"], atom["bytes"], atom["sha256"])
            if atom_leaf.hex() != atom["fmo_leaf"]:
                errors.append(f"LEAF:{atom['path']}")
            groups.setdefault(atom["group"], []).append((atom["path"], atom_leaf))

        root_hash, _ = fmo_root(groups)
        if root_hash != entry["bp_root"]:
            errors.append(f"BP_ROOT:{entry['bp_id']}")
        if root_hash != doc.get("bp_root"):
            errors.append(f"BP_DOC_ROOT:{entry['bp_id']}")
        if doc.get("breakpoint_root") != doc.get("bp_root"):
            errors.append(f"BREAKPOINT_ROOT_ALIAS:{entry['bp_id']}")

        mmr_leaf_bytes = mmr_leaf(i, entry["bp_id"], root_hash, file_sha)
        leaves.append(mmr_leaf_bytes)
        if mmr_leaf_bytes.hex() != entry["mmr_leaf"]:
            errors.append(f"MMR_LEAF:{entry['bp_id']}")
        root_after, peaks_after = mmr_root(leaves)
        if root_after != entry["mmr_root_after"]:
            errors.append(f"MMR_ROOT_AFTER:{entry['bp_id']}")
        if entry.get("mmr_peaks_after") is not None and peaks_after != entry["mmr_peaks_after"]:
            errors.append(f"MMR_PEAKS_AFTER:{entry['bp_id']}")

    final_root, _ = mmr_root(leaves)
    return {
        "lineage_id": ledger.get("lineage_id"),
        "mmr_size": len(leaves),
        "mmr_root": final_root,
    }, errors


def main() -> int:
    summary, errors = verify_lineage(ROOT, LP)
    print("COMP_LINEAGE_ID=" + str(summary["lineage_id"]))
    print("COMP_MMR_SIZE=" + str(summary["mmr_size"]))
    print("COMP_MMR_ROOT=" + str(summary["mmr_root"]))
    print("COMP_BREAKPOINT_VERIFY=" + ("PASS" if not errors else "FAIL"))
    for error in errors:
        print(error)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
