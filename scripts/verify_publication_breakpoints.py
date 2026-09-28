#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

LEDGER = ROOT / "governance/publication/MMR_LEDGER.json"

def git_bytes(commit, path):
    p = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    return p.stdout if p.returncode == 0 else None

def introduction_commit(path):
    p = subprocess.run(
        ["git", "log", "--diff-filter=A", "--reverse", "--format=%H", "--", path],
        cwd=ROOT, capture_output=True, text=True
    )
    rows = [x for x in p.stdout.splitlines() if x.strip()]
    return rows[0] if rows else None

if not LEDGER.exists():
    print("PUBLICATION_MMR_CHAIN_VERIFY=FAIL")
    print("PUBLICATION_ATOM_REPLAY_VERIFY=FAIL")
    print("PUBLICATION_BREAKPOINT_VERIFY=FAIL")
    print("NO_LEDGER")
    raise SystemExit(2)

led = json.loads(LEDGER.read_text())
integrity_errors = []
custody_gaps = []
leaves = []
historical = []

for i, e in enumerate(led["entries"]):
    p = ROOT / e["bp_file"]
    if not p.exists():
        integrity_errors.append("MISSING_BP_FILE:" + e["bp_file"])
        continue
    d = json.loads(p.read_text())
    bp_commit = introduction_commit(e["bp_file"])
    groups = {}

    for a in d["atoms"]:
        q = ROOT / a["path"]
        ok = False
        if q.exists():
            sha, n = sha256_file(q)
            ok = (sha == a["sha256"] and n == a["bytes"])
        if not ok and bp_commit:
            blob = git_bytes(bp_commit, a["path"])
            if blob is not None:
                sha = hashlib.sha256(blob).hexdigest()
                n = len(blob)
                if sha == a["sha256"] and n == a["bytes"]:
                    ok = True
                    historical.append({
                        "bp_id": e["bp_id"],
                        "path": a["path"],
                        "git_commit": bp_commit,
                    })
        if not ok:
            custody_gaps.append({
                "bp_id": e["bp_id"],
                "path": a["path"],
                "sha256": a["sha256"],
                "bytes": a["bytes"],
            })

        lf = leaf(a["path"], a["bytes"], a["sha256"])
        if lf.hex() != a["fmo_leaf"]:
            integrity_errors.append("LEAF:" + a["path"])
        groups.setdefault(a["group"], []).append((a["path"], lf))

    root, _ = fmo_root(groups)
    if root != d["bp_root"] or root != e["bp_root"]:
        integrity_errors.append("ROOT:" + e["bp_id"])

    fsha, _ = sha256_file(p)
    if fsha != e["bp_file_sha256"]:
        integrity_errors.append("BP_FILE:" + e["bp_id"])

    mlf = mmr_leaf(i, e["bp_id"], root, fsha)
    leaves.append(mlf)
    if mlf.hex() != e["mmr_leaf"]:
        integrity_errors.append("MMR_LEAF:" + e["bp_id"])

    mr, _ = mmr_root(leaves)
    if mr != e["mmr_root_after"]:
        integrity_errors.append("MMR_ROOT:" + e["bp_id"])

    print(e["bp_id"], root, e["mmr_root_after"])

final, _ = mmr_root(leaves)
chain_state = "PASS" if not integrity_errors else "FAIL"
atom_state = "PASS" if not custody_gaps else "PARTIAL"
overall = "PASS" if chain_state == "PASS" and atom_state == "PASS" else ("PARTIAL" if chain_state == "PASS" else "FAIL")

print("HISTORICAL_ATOMS_RECOVERED_FROM_GIT=" + str(len(historical)))
for x in historical:
    print("HISTORICAL_ATOM", x["bp_id"], x["path"], x["git_commit"])
print("PUBLICATION_MMR_SIZE=" + str(len(leaves)))
print("PUBLICATION_MMR_ROOT=" + final)
print("PUBLICATION_MMR_CHAIN_VERIFY=" + chain_state)
print("PUBLICATION_ATOM_REPLAY_VERIFY=" + atom_state)
print("PUBLICATION_CUSTODY_GAP_COUNT=" + str(len(custody_gaps)))
print("PUBLICATION_BREAKPOINT_VERIFY=" + overall)

for x in custody_gaps:
    print("ATOM_UNRECOVERABLE", x["bp_id"], x["path"], x["sha256"], x["bytes"])
for x in integrity_errors:
    print(x)

if integrity_errors:
    raise SystemExit(2)
if custody_gaps:
    raise SystemExit(3)
raise SystemExit(0)
