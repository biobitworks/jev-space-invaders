"""Append-only breakpoints: atoms (FCOs) -> breakpoint root -> MMR ledger.

A breakpoint JSON commits to its atoms by an FMO root. It never contains its own
MMR position (that would be circular); governance/MMR_LEDGER.json does.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

ROOT = Path(__file__).resolve().parents[1]
BP_DIR = ROOT / "governance" / "breakpoints"
LEDGER = ROOT / "governance" / "MMR_LEDGER.json"
PRIVATE_PREFIX = "artifacts/private/"


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "UNKNOWN"


def atom_record(rel_path: str, kind: str, group: str) -> dict:
    p = ROOT / rel_path
    sha, n = sha256_file(p)
    return {"path": rel_path, "kind": kind, "group": group, "bytes": n, "sha256": sha,
            "location": "private" if rel_path.startswith(PRIVATE_PREFIX) else "public",
            "fmo_leaf": leaf(rel_path, n, sha).hex()}


def atoms_root(atoms: list[dict]) -> tuple[str, dict[str, str]]:
    groups: dict[str, list] = {}
    for a in atoms:
        groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(a["fmo_leaf"])))
    return fmo_root(groups)


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"schema": "VITHIA_MMR_LEDGER_V1",
            "protocol": "docs/BREAKPOINT_PROTOCOL.md",
            "entries": []}


def _append(ledger: dict, bp_id: str, bp_file: Path, bp_root: str, kind: str) -> dict:
    seq = len(ledger["entries"])
    fsha, _ = sha256_file(bp_file)
    lf = mmr_leaf(seq, bp_id, bp_root, fsha)
    leaves = [bytes.fromhex(e["mmr_leaf"]) for e in ledger["entries"]] + [lf]
    root, peaks = mmr_root(leaves)
    entry = {"seq": seq, "bp_id": bp_id, "bp_file": str(bp_file.relative_to(ROOT)),
             "bp_file_sha256": fsha, "bp_root": bp_root, "root_kind": kind,
             "mmr_leaf": lf.hex(), "mmr_size": len(leaves), "mmr_root_after": root,
             "mmr_peaks_after": peaks}
    ledger["entries"].append(entry)
    return entry


def latest_number() -> int:
    nums = [int(f.name[:4]) for f in BP_DIR.glob("[0-9][0-9][0-9][0-9]-*.json")]
    return max(nums) if nums else 0


def ensure_legacy(ledger: dict) -> None:
    """Breakpoints without atom roots (all written before this protocol, or by another
    tool) enter the ledger in file order as a single atom: the breakpoint file itself."""
    have = {e["bp_file"] for e in ledger["entries"]}
    for f in sorted(BP_DIR.glob("[0-9][0-9][0-9][0-9]-*.json")):
        if str(f.relative_to(ROOT)) in have:
            continue
        doc = json.loads(f.read_text())
        if doc.get("root_kind") == "FMO_V1_BREAKPOINT_ATOMS":
            raise SystemExit(f"{f.name} has atom roots but is not in the ledger; refusing to guess its order")
        bp_id = doc.get("breakpoint_id") or f"UFA-JEV-BP-{f.name[:4]}"
        rel = str(f.relative_to(ROOT))
        sha, n = sha256_file(f)
        root, _ = fmo_root({"legacy": [(rel, leaf(rel, n, sha))]})
        _append(ledger, bp_id, f, root, "LEGACY_SINGLE_ATOM")


def create_breakpoint(slug: str, state: str, atoms: list[dict], body: dict) -> dict:
    """Numbered after the highest existing breakpoint; parent is that breakpoint."""
    prev = latest_number()
    number, parent = prev + 1, f"UFA-JEV-BP-{prev:04d}"
    bp_id = f"UFA-JEV-BP-{number:04d}"
    root, group_roots = atoms_root(atoms)
    doc = {"breakpoint_id": bp_id, "parent": parent, "state": state, "project": "VITHIA_SPACE",
           "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "git_head_at_creation": git_head(),
           "root_kind": "FMO_V1_BREAKPOINT_ATOMS", "bp_root": root, "group_roots": group_roots,
           "atoms": atoms, **body,
           "claim_ceiling": "IDENTITY_AND_INCLUSION_ONLY; hashes do not establish correctness",
           "signature_state": "NOT_SIGNED"}
    path = BP_DIR / f"{number:04d}-{slug}.json"
    if path.exists():
        raise SystemExit(f"{path} exists; breakpoints are append-only. Create a successor.")
    ledger = load_ledger()
    ensure_legacy(ledger)  # before writing the new file, so it is not mistaken for legacy
    path.write_text(json.dumps(doc, indent=2) + "\n")
    entry = _append(ledger, bp_id, path, root, doc["root_kind"])
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")
    return {"bp_file": str(path.relative_to(ROOT)), "bp_root": root, **entry}
