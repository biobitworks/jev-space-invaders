#!/usr/bin/env python3
"""HARNESS_AUTOPUSH breakpoint (numbered after the latest existing breakpoint). Run AFTER: python scripts/run_games.py --decider scripted --seeds 1 2 3 4 5

Gate: >= 5 scripted runs in results.json, each with its own "results: run <n>," commit
reachable from origin/<default>, each trace file present with matching sha256, and
the results file passes validation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.breakpoints import atom_record, create_breakpoint  # noqa: E402
from src.validate import check_file  # noqa: E402


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:
    git("fetch", "--quiet", "origin")
    import os
    default = "origin/" + os.environ["VITHIA_BRANCH"] if os.environ.get("VITHIA_BRANCH") else (git("symbolic-ref", "--short", "refs/remotes/origin/HEAD") or "origin/main")
    d = json.loads((ROOT / "results.json").read_text())
    summary = check_file(ROOT / "results.json")
    scripted = [r for r in d["runs"] if r.get("provider") == "none"]
    checks = []
    for r in scripted:
        commit = git("log", default, "--format=%H", "-F", f"--grep=results: run {r['run']},")
        t = ROOT / r["trace_file"]
        sha_ok = t.exists() and hashlib.sha256(t.read_bytes()).hexdigest() == r["trace_sha256"]
        checks.append({"run": r["run"], "seed": r["seed"], "score": r["score"],
                       "pushed_commit": commit.splitlines()[0] if commit else None, "trace_sha_ok": sha_ok})
    gate = len(checks) >= 5 and all(c["pushed_commit"] and c["trace_sha_ok"] for c in checks)
    atoms = [atom_record(p, "CodeFCO", "code") for p in ("scripts/verify_episode_mmr.py",
        "src/harness.py", "src/deciders.py", "src/perception.py", "src/validate.py", "src/envcfg.py",
        "src/actions.py", "scripts/run_games.py", "scripts/bp_harness.py")]
    atoms.append(atom_record("results.json", "ResultsFCO", "results"))
    atoms += [atom_record(r["trace_file"], "EpisodeTraceFCO", "traces") for r in scripted]
    out = create_breakpoint("harness-autopush",
                            "HARNESS_AUTOPUSH_PASS" if gate else "HARNESS_AUTOPUSH_FAIL", atoms, {
        "fcg_edges": [
            {"src": "Harness", "rel": "EXECUTED_WITH", "dst": "RuntimeSourceDataset_V2"},
            {"src": "EpisodeTrace", "rel": "RESULTS_IN", "dst": "ResultsFCO"},
            {"src": "ResultsFCO", "rel": "PUBLISHED_TO", "dst": f"git:{default}"}],
        "executed": ["scripted-policy episodes", "per-game results.json append + commit + push"],
        "observed": {"scripted_runs": checks, "results_summary": summary},
        "labels": "scripted runs are provider=none / served_model=scripted-policy: NON-JEV, do not count toward Performance",
        "not_tested": ["JEV", "OpenJev", "LLM baseline"],
        "next_action": "Vithia preprocessor (Anticube, CA field, Minesweeper, path integral)"})
    print(json.dumps({"gate": "PASS" if gate else "FAIL", "runs_checked": len(checks),
                      **{k: out[k] for k in ("bp_id", "bp_file", "bp_root", "mmr_size", "mmr_root_after")}}, indent=2))
    return 0 if gate else 3


if __name__ == "__main__":
    raise SystemExit(main())
