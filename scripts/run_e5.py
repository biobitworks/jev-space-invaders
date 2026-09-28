#!/usr/bin/env python3
"""E5 ladder stages (docs/prereg/E5_LADDER.md). Each stage seals a breakpoint and, with --push, pushes
and verifies the remote. Reuses the sealed scripts/run_experiment.py helpers without modifying them.

  python scripts/run_e5.py probe  --push                       # 20 SETUP_SMOKE calls -> latency receipt
  python scripts/run_e5.py prereg --budget-hours 10 --push      # freeze arms, seeds, MAX_DECISIONS from probe
  python scripts/run_e5.py run-1p --push                        # OJ/VS seeds 1-5, interleaved, one BP at the end
  python scripts/run_e5.py rom-gate --rom-dir <dir> --push      # 2P runtime successor (or ROM_GATE_BLOCKED)
  python scripts/run_e5.py run-2p --rom-dir <dir> --push        # M1, M2, M2', M3 (one BP per matchup)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.run_experiment as rx  # noqa: E402
from experiments import e5_2p, e5_episodes  # noqa: E402
from src.openjev_client import OpenJevDecider  # noqa: E402

EV = ROOT / "evidence" / "e5"
OUT = ROOT / "results" / "vita01" / "e5"
SEEDS = [1, 2, 3, 4, 5]
CODE = ["experiments/e5_episodes.py", "experiments/e5_2p.py", "scripts/run_e5.py", "src/openjev_client.py",
        "experiments/e4b_ablation.py", "experiments/e4a_snapshots.py", "src/perception.py", "src/envcfg.py"]


def decider():
    man = json.loads((ROOT / "evidence/openjev/RUNTIME_MANIFEST.json").read_text())
    if man.get("OPENJEV_LOADED") != "YES":
        raise SystemExit("OPENJEV_LOADED != YES")
    return OpenJevDecider(man["endpoint"].rsplit("/v1/systemone", 1)[0], "openjev", max_retries=2, timeout_s=120)


def seal(slug, state, paths_for_atoms, body, push, commit_paths):
    atoms = [rx.atom_record(str(p.relative_to(ROOT)) if isinstance(p, Path) else p, "E5FCO", "e5") for p in paths_for_atoms]
    out = rx.create_breakpoint(slug, state, atoms, {"experiment_id": "E5", "pre_mmr_root": rx.pre_mmr(), **body})
    print(json.dumps({k: out[k] for k in ("bp_id", "bp_root", "mmr_size", "mmr_root_after")}, indent=2))
    if push:
        print("REMOTE_VERIFIED=" + rx.publish(f"e5: {slug} ({out['bp_id']})", ["governance", *commit_paths]))
    return out


def frozen():
    for f in sorted(rx.BP_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("stage") == "E5_PREREG":
            fz = d
    try:
        fz
    except NameError:
        raise SystemExit("E5 prereg breakpoint missing")
    import hashlib
    for a in fz["atoms"]:
        if hashlib.sha256((ROOT / a["path"]).read_bytes()).hexdigest() != a["sha256"]:
            raise SystemExit(f"frozen atom changed: {a['path']}")
    return fz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["probe", "prereg", "run-1p", "rom-gate", "run-2p"])
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--branch", default="vithia-space")
    ap.add_argument("--budget-hours", type=float, default=10.0)
    ap.add_argument("--rom-dir")
    a = ap.parse_args()
    rx.BRANCH = a.branch
    if a.push:
        rx.preflight()
    EV.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.stage == "probe":
        pr = e5_episodes.latency_probe(decider())
        (EV / "LATENCY_PROBE.json").write_text(json.dumps(pr, indent=2) + "\n")
        print(pr)
        seal("e5-latency-probe", "SETUP_SMOKE_NON_EXPERIMENTAL", [EV / "LATENCY_PROBE.json"], {"stage": "E5_PROBE"}, a.push, ["evidence/e5"])
    elif a.stage == "prereg":
        pr = json.loads((EV / "LATENCY_PROBE.json").read_text())
        # calls: 1P 10 episodes x 1 call; 2P 20 episodes x 2 calls -> 50 episode-call units
        max_dec = max(50, math.floor(a.budget_hours * 3600 * 1000 / (pr["p95_ms"] * 1.15) / 50))
        cfg = {"arms": e5_episodes.ARMS, "seeds": SEEDS, "order": "interleave OJ,VS by seed; 2P M1,M2,M2',M3 by seed",
               "max_decisions": max_dec, "budget_hours": a.budget_hours, "probe_p95_ms": pr["p95_ms"],
               "ontology_ids": e5_2p.ONTOLOGY_IDS, "question_1p": "src/deciders.MOVE_QUESTION", "question_2p": e5_2p.QUESTION_2P,
               "tests": {"1p": "Wilcoxon signed-rank VS vs OJ score, n=5 (min two-sided p=0.0625: SUPPORTED impossible at 0.05; "
                                "report effect sizes + bootstrap CI; claim FAIL_TO_REJECT_H0 or DESCRIPTIVE_ONLY)"},
               "labels": ["provider=openjev", "NON_TYPESAFE_JEV"]}
        (EV / "E5_PREREG_CONFIG.json").write_text(json.dumps(cfg, indent=2) + "\n")
        print({"max_decisions": max_dec})
        seal("e5-prereg", "PREREG_SEALED", ["docs/prereg/E5_LADDER.md", EV / "E5_PREREG_CONFIG.json",
             "evidence/openjev/RUNTIME_MANIFEST.json", *CODE], {"stage": "E5_PREREG"}, a.push, ["evidence/e5"])
    elif a.stage == "run-1p":
        fz = frozen()
        cfg = json.loads((EV / "E5_PREREG_CONFIG.json").read_text())
        dec, runs, files = decider(), [], []
        for seed in SEEDS:
            for arm in ("OJ", "VS"):
                run, trace = e5_episodes.run_episode(arm, dec, seed, cfg["max_decisions"])
                tp = OUT / f"1p_{arm}_seed{seed}.jsonl.gz"
                run["trace_sha256"] = e5_episodes.write_trace(tp, trace)
                runs.append(run)
                files.append(tp)
                print(json.dumps({k: run[k] for k in ("arm", "seed", "score", "decisions", "truncated", "latency_ms_p50")}))
        rp = OUT / "E5_1P_RUNS.json"
        rp.write_text(json.dumps({"prereg_breakpoint": fz["breakpoint_id"], "runs": runs}, indent=2) + "\n")
        seal("e5-1p-result", "EXECUTED_RESULT_ANALYSIS_PENDING", [rp, *files], {"stage": "E5_1P", "prereg": fz["breakpoint_id"]},
             a.push, ["results/vita01/e5"])
    elif a.stage == "rom-gate":
        g = e5_2p.rom_gate(a.rom_dir)
        (EV / "ROM_GATE.json").write_text(json.dumps(g, indent=2) + "\n")
        print(g)
        seal("e5-2p-rom-gate", g["state"], [EV / "ROM_GATE.json"], {"stage": "E5_ROM_GATE"}, a.push, ["evidence/e5"])
    elif a.stage == "run-2p":
        fz = frozen()
        g = e5_2p.rom_gate(a.rom_dir)
        if g["state"] != "ROM_PRESENT":
            raise SystemExit(f"2P blocked: {g['reason']}")
        from pettingzoo.atari import space_invaders_v2

        from src.perception import Perception
        cfg = json.loads((EV / "E5_PREREG_CONFIG.json").read_text())
        dec = decider()
        matchups = {"M1": ("VS", "VS"), "M2": ("VS", "OJ"), "M2prime": ("OJ", "VS"), "M3": ("OJ", "OJ")}
        for name, (s0, s1) in matchups.items():
            summaries, files = [], []
            for seed in SEEDS:
                summ, rows = e5_2p.run_match(lambda: space_invaders_v2.parallel_env(auto_rom_install_path=a.rom_dir),
                                             Perception, {"first_0": dec, "second_0": dec}, {"first_0": s0, "second_0": s1},
                                             seed, cfg["max_decisions"])
                tp = OUT / f"2p_{name}_seed{seed}.jsonl.gz"
                summ["trace_sha256"] = e5_episodes.write_trace(tp, rows)
                summaries.append(summ)
                files.append(tp)
                print(json.dumps({"matchup": name, **{k: summ[k] for k in ("seed", "scores", "decisions")}}))
            sp = OUT / f"E5_2P_{name}.json"
            sp.write_text(json.dumps({"matchup": name, "seats": [s0, s1], "rom": g, "runs": summaries}, indent=2) + "\n")
            seal(f"e5-2p-{name.lower()}", "EXECUTED_RESULT_ANALYSIS_PENDING", [sp, *files],
                 {"stage": "E5_2P", "matchup": name, "prereg": fz["breakpoint_id"]}, a.push, ["results/vita01/e5"])


if __name__ == "__main__":
    main()
