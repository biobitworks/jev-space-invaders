"""Create UFA-JEV-COMP-BP-* qualified competition breakpoints.

Mirrors src/breakpoints.py's atom-root + MMR mechanics but writes to the
qualified lineage's own ledger (governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json)
and breakpoint directory (governance/competition/breakpoints/), never touching
the legacy UFA-JEV-BP-* chain. Schema matches what
scripts/verify_competition_lineage.py independently verifies.
"""
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

ROOT = Path(__file__).resolve().parents[1]
BP_DIR = ROOT / "governance" / "competition" / "breakpoints"
LEDGER = ROOT / "governance" / "lineage" / "UFA_JEV_COMP_MMR_LEDGER.json"
LINEAGE_ID = "UFA-JEV-COMP"
BRANCH = "competition/final-integration-v01"


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def atom_record(rel_path: str, kind: str, group: str) -> dict:
    p = ROOT / rel_path
    sha, n = sha256_file(p)
    return {"path": rel_path, "kind": kind, "group": group, "bytes": n, "sha256": sha,
            "location": "public", "fmo_leaf": leaf(rel_path, n, sha).hex()}


def atoms_root(atoms: list[dict]) -> tuple[str, dict[str, str]]:
    groups: dict[str, list] = {}
    for a in atoms:
        groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(a["fmo_leaf"])))
    return fmo_root(groups)


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text())


def latest_number() -> int:
    nums = [int(f.name[:4]) for f in BP_DIR.glob("[0-9][0-9][0-9][0-9]-*.json")]
    return max(nums) if nums else 0


IDENTITY_FIELDS = frozenset({"lineage_id", "branch", "breakpoint_id", "parent_root",
                              "bp_root", "breakpoint_root", "root_kind", "atoms", "group_roots"})


def create(slug: str, state: str, atoms: list[dict], body: dict) -> dict:
    clobbering = IDENTITY_FIELDS & set(body)
    if clobbering:
        raise ValueError(f"body must not set identity fields: {sorted(clobbering)}")
    ledger = load_ledger()
    number = latest_number() + 1
    bp_id = f"{LINEAGE_ID}-BP-{number:04d}"
    prior = ledger["entries"][-1] if ledger["entries"] else None
    parent_root = prior["mmr_root_after"] if prior else None
    root, group_roots = atoms_root(atoms)
    doc = {
        "schema": "UFA_JEV_QUALIFIED_BREAKPOINT_V1",
        "lineage_id": LINEAGE_ID,
        "branch": BRANCH,
        "breakpoint_id": bp_id,
        "state": state,
        "project": "VITHIA_SPACE",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head_at_creation": git_head(),
        "root_kind": "FMO_V1_BREAKPOINT_ATOMS",
        "bp_root": root,
        "breakpoint_root": root,
        "parent_root": parent_root,
        "group_roots": group_roots,
        "atoms": atoms,
        "historical_mutation_performed": False,
        "mmr_reconciliation_performed": False,
        **body,
        "claim_ceiling": "IDENTITY_AND_INCLUSION_ONLY; hashes do not establish correctness",
        "signature_state": "NOT_SIGNED",
    }
    path = BP_DIR / f"{number:04d}-{slug}.json"
    if path.exists():
        raise SystemExit(f"{path} exists; breakpoints are append-only.")
    path.write_text(json.dumps(doc, indent=2) + "\n")
    fsha, _ = sha256_file(path)
    seq = len(ledger["entries"])
    lf = mmr_leaf(seq, bp_id, root, fsha)
    leaves = [bytes.fromhex(e["mmr_leaf"]) for e in ledger["entries"]] + [lf]
    mroot, peaks = mmr_root(leaves)
    entry = {"seq": seq, "bp_id": bp_id, "bp_file": str(path.relative_to(ROOT)),
             "bp_file_sha256": fsha, "bp_root": root, "branch": BRANCH, "lineage_id": LINEAGE_ID,
             "parent_root": parent_root, "root_kind": "FMO_V1_BREAKPOINT_ATOMS",
             "mmr_leaf": lf.hex(), "mmr_size": len(leaves), "mmr_root_after": mroot,
             "mmr_peaks_after": peaks}
    ledger["entries"].append(entry)
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")
    return {"bp_file": str(path.relative_to(ROOT)), "bp_id": bp_id, **entry}
