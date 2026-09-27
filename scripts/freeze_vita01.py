#!/usr/bin/env python3
"""Freeze the 0-Vita-1 confirmatory protocol before any confirmatory execution.

Seals: type contract, confirmatory prereg, all prereg docs, schemas, kernels, experiment code,
runner, pinned requirements, type-error tests, and the test log from this machine.
With --push: commits, pushes to --branch, fetches, verifies the commit is on the remote.
Refuses if tests fail, secret scan fails, or breakpoint verification fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_experiment as rx  # noqa: E402
from src.breakpoints import atom_record, create_breakpoint  # noqa: E402

GROUP = {"vita01/": "contract", "docs/prereg/": "prereg", "schemas/": "schema", "requirements.txt": "code"}


def group_of(path: str) -> str:
    for k, v in GROUP.items():
        if path.startswith(k):
            return v
    return "code"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--branch", default="main")
    a = ap.parse_args()
    rx.BRANCH = a.branch
    if a.push:
        rx.preflight()
    log = ROOT / "evidence" / "vita01" / "FREEZE_TEST_LOG.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    s = subprocess.run([sys.executable, "scripts/secret_scan.py"], cwd=ROOT, capture_output=True, text=True)
    log.write_text("## pytest\n" + t.stdout[-4000:] + "\n## secret_scan\n" + s.stdout)
    if t.returncode or s.returncode:
        print(log.read_text())
        raise SystemExit("tests or secret scan failed: not freezing")
    atoms = [atom_record(p, "FrozenProtocolFCO", group_of(p)) for p in rx.freeze_files()]
    atoms.append(atom_record(str(log.relative_to(ROOT)), "TestLogFCO", "evidence"))
    out = create_breakpoint("vita01-confirmatory-freeze", "VITA01_CONFIRMATORY_PROTOCOL_FROZEN", atoms, {
        "stage": "VITA01_FREEZE", "protocol": "0-Vita-1", "mode": "POST_REHEARSAL_PROSPECTIVE_CONFIRMATORY",
        "blind_preregistration": False, "exploratory_rehearsal_preceded": True,
        "evidence_level": "SIMULATED", "biological_transfer": "NOT_TESTED",
        "fcg_edges": [{"src": "VITA01_CONFIRMATORY_PREREGISTRATION", "rel": "SUPERSEDES",
                       "dst": "EXPLORATORY_REHEARSAL (preserved, not rewritten)"}]})
    print({k: out[k] for k in ("bp_id", "bp_root", "mmr_root_after")})
    if a.push:
        subprocess.run([sys.executable, "scripts/build_registries.py"], cwd=ROOT, check=True)
        head = rx.publish(f"vita01: freeze confirmatory protocol ({out['bp_id']})", ["governance", "evidence/vita01", "vita01"])
        print(f"REMOTE_VERIFIED={head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
