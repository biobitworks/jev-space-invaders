#!/usr/bin/env python3
"""Governed S01 experiment ladder.

  python scripts/run_experiment.py E0 --stage prereg  --push   # freeze input + prereg -> breakpoint -> push
  python scripts/run_experiment.py E0 --stage execute --push   # run -> output dataset + receipt -> breakpoint -> push
  python scripts/run_experiment.py E0 --stage all --push
  python scripts/run_experiment.py E4A --stage prereg --push   # input freeze only (no decider calls)

Breakpoint numbers are allocated dynamically. With --push the runner refuses to start unless
HEAD == origin/main on a clean main; after pushing it fetches and verifies the remote contains
the commit. Without --push it writes locally (rehearsal) and commits nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.breakpoints import BP_DIR, LEDGER, atom_record, create_breakpoint  # noqa: E402
from src.s01.canon import git_head  # noqa: E402
from src.s01.protocol import validate  # noqa: E402

EXPS = {
    "E0": ("experiments.e0_babel", ["E0_ADDRESSABILITY.md"]),
    "E1": ("experiments.e1_eca", ["E1_ECA.md"]),
    "E2": ("experiments.e2_life", ["E2_LIFE.md"]),
    "E3": ("experiments.e3_minesweeper", ["E3_MINESWEEPER.md"]),
    "E4A": ("experiments.e4a_snapshots", ["E4A_SPACE_INVADERS_SNAPSHOTS.md"]),
}
SHARED_CODE = ["src/s01/canon.py", "src/s01/protocol.py", "src/fmo.py", "src/breakpoints.py", "experiments/common.py",
               "scripts/run_experiment.py", "schemas/s01/S01_CONTEXT_PACKET_V1.json",
               "schemas/s01/S01_DECISION_RECEIPT_V1.json", "schemas/s01/S01_TRANSITION_RECEIPT_V1.json",
               "schemas/s01/S01_EXPERIMENT_RECEIPT_V1.json"]
REF = ROOT / "evidence" / "s01" / "REFERENCE_RUNTIME_DIGESTS.json"


def git(*a, check=False):
    p = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f"git {' '.join(a)} failed:\n{p.stderr}")
    return p.stdout.strip()


def preflight():
    git("fetch", "--quiet", "origin", check=True)
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise SystemExit("not on main")
    if git("status", "--porcelain"):
        raise SystemExit("worktree not clean")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise SystemExit("HEAD != origin/main: another writer moved main or local work is unpushed. Reconcile first.")
    v = subprocess.run([sys.executable, "scripts/verify_breakpoints.py"], cwd=ROOT, capture_output=True, text=True)
    if v.returncode:
        raise SystemExit("breakpoint verification failed before experiment:\n" + v.stdout[-2000:])


def pre_mmr():
    if not LEDGER.exists():
        return None
    e = json.loads(LEDGER.read_text())["entries"]
    return e[-1]["mmr_root_after"] if e else None


def publish(msg: str, paths: list[str]) -> str:
    git("add", *paths, check=True)
    git("commit", "-m", msg, check=True)
    git("push", "origin", "main", check=True)
    head = git("rev-parse", "HEAD")
    git("fetch", "--quiet", "origin", check=True)
    if subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"], cwd=ROOT).returncode:
        raise SystemExit(f"remote verification failed: {head} not on origin/main")
    return head


def dataset_atoms(dataset_id: str, group: str) -> list[dict]:
    d = ROOT / "data" / "s01" / dataset_id
    return [atom_record(str(p.relative_to(ROOT)), "DatasetFileFCO" if p.name != "MANIFEST.json" else "DatasetManifestFCO", group)
            for p in sorted(d.iterdir()) if p.is_file()]


def rows_sha(dataset_id: str) -> str:
    return hashlib.sha256((ROOT / "data" / "s01" / dataset_id / "rows.jsonl").read_bytes()).hexdigest()


def find_prereg(exp: str) -> dict | None:
    found = None
    for f in sorted(BP_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("experiment_id") == exp and d.get("stage") == "PREREG":
            found = d
    return found


def stage_prereg(exp: str, push: bool) -> None:
    mod_name, docs = EXPS[exp]
    mod = importlib.import_module(mod_name)
    pre = pre_mmr()
    man = mod.build_input()
    atoms = [atom_record(f"docs/prereg/{x}", "PreregistrationFCO", "prereg") for x in ["COMMON.md", *docs]]
    atoms += dataset_atoms(mod.IN_ID, "input_dataset")
    atoms += [atom_record(c, "CodeFCO", "code") for c in sorted(set(mod.CODE + SHARED_CODE))]
    out = create_breakpoint(f"{exp.lower()}-prereg", "PREREG_SEALED" if exp != "E4A" else "INPUT_FROZEN_NO_DECIDER_CALLS",
                            atoms, {"experiment_id": mod.EXP, "stage": "PREREG", "input_dataset": {"dataset_id": mod.IN_ID, "fmo_root": man["fmo_root"]},
                                    "pre_mmr_root": pre,
                                    "fcg_edges": [{"src": mod.IN_ID, "rel": "FROZEN_UNDER", "dst": "PreregistrationFCO"}],
                                    "claim_ceiling_note": "sealing proves identity of the prereg text, not that it predates rehearsal executions (see docs/prereg/COMMON.md)"})
    print(json.dumps({k: out[k] for k in ("bp_id", "bp_file", "bp_root", "mmr_root_after")}, indent=2))
    if push:
        head = publish(f"prereg: {exp} input dataset {mod.IN_ID} sealed ({out['bp_id']})",
                       ["data/s01", "docs/prereg", "governance"])
        print(f"REMOTE_VERIFIED={head}")


def stage_execute(exp: str, push: bool) -> None:
    mod_name, _ = EXPS[exp]
    mod = importlib.import_module(mod_name)
    if exp == "E4A":
        raise SystemExit("E4A has no local execute stage; decider batches follow the credit ladder")
    pre_bp = find_prereg(mod.EXP)
    if pre_bp is None:
        raise SystemExit(f"no PREREG breakpoint for {mod.EXP}; run --stage prereg first")
    for a in pre_bp["atoms"]:
        if a["group"] == "input_dataset":
            if hashlib.sha256((ROOT / a["path"]).read_bytes()).hexdigest() != a["sha256"]:
                raise SystemExit(f"input dataset changed since prereg: {a['path']}")
    pre = pre_mmr()
    res = mod.run()
    ref = json.loads(REF.read_text()).get(exp, {}) if REF.exists() else {}
    in_sha, out_sha = rows_sha(mod.IN_ID), rows_sha(mod.OUT_ID)
    replay = {"reference_runtime": ref.get("runtime"),
              "input_rows_equal": (in_sha == ref.get("input_rows_sha256")) if ref else None,
              "output_rows_equal": (out_sha == ref.get("output_rows_sha256")) if ref else None}
    replay["replay_level"] = ("REPLAY_LEVEL_4" if replay["input_rows_equal"] and replay["output_rows_equal"]
                              else "REPLAY_LEVEL_2" if ref else "NOT_COMPARED")
    receipt = {"schema": "S01_EXPERIMENT_RECEIPT_V1", "experiment_id": mod.EXP, "question": res["question"],
               "preregistration": res["preregistration"], "prereg_breakpoint": pre_bp["breakpoint_id"],
               "input_dataset": {"dataset_id": mod.IN_ID, "fmo_root": pre_bp["input_dataset"]["fmo_root"], "rows_sha256": in_sha},
               "output_dataset": {"dataset_id": mod.OUT_ID, "fmo_root": res["output_manifest"]["fmo_root"], "rows_sha256": out_sha},
               "code_commit": git_head(), "terminal_state": res["terminal_state"], "claims": res["claims"],
               "not_tested": res.get("not_tested", []), "replay": replay, "note": res.get("note")}
    validate(receipt, "S01_EXPERIMENT_RECEIPT_V1")
    rdir = ROOT / "evidence" / "s01" / mod.EXP
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "EXPERIMENT_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    atoms = dataset_atoms(mod.OUT_ID, "output_dataset")
    atoms.append(atom_record(str((rdir / "EXPERIMENT_RECEIPT.json").relative_to(ROOT)), "ExperimentReceiptFCO", "receipt"))
    out = create_breakpoint(f"{exp.lower()}-result", f"RESULT_{res['terminal_state']}", atoms,
                            {"experiment_id": mod.EXP, "stage": "RESULT", "prereg_breakpoint": pre_bp["breakpoint_id"],
                             "pre_mmr_root": pre, "terminal_state": res["terminal_state"],
                             "claims_summary": [{"id": c["id"], "state": c["state"]} for c in res["claims"]],
                             "replay": replay,
                             "fcg_edges": [{"src": mod.OUT_ID, "rel": "DERIVED_FROM", "dst": mod.IN_ID},
                                           {"src": "ExperimentReceipt", "rel": "EXECUTED_UNDER", "dst": pre_bp["breakpoint_id"]}]})
    print(json.dumps({"terminal_state": res["terminal_state"], "claims": [(c["id"], c["state"]) for c in res["claims"]],
                      "replay": replay["replay_level"], **{k: out[k] for k in ("bp_id", "bp_root", "mmr_root_after")}}, indent=2))
    if push:
        head = publish(f"result: {exp} {res['terminal_state']} ({out['bp_id']})", ["data/s01", "evidence/s01", "governance"])
        print(f"REMOTE_VERIFIED={head}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=list(EXPS))
    ap.add_argument("--stage", choices=["prereg", "execute", "all"], default="all")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    if a.push:
        preflight()
    if a.stage in ("prereg", "all"):
        stage_prereg(a.exp, a.push)
        if a.push:
            preflight()
    if a.stage in ("execute", "all") and a.exp != "E4A":
        stage_execute(a.exp, a.push)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
