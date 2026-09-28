#!/usr/bin/env python3
"""E4B_LATENCY_DECISION and E4C_QUALITY stages. Reuses the sealed scripts/run_experiment.py (imported, never modified) and adds:
runtime-identity atoms, the OPENJEV_LOADED gate, and a code/runtime atom check before execution.

  python scripts/run_e4b.py --stage prereg  --push      # E4B freeze (needs OPENJEV_LOADED=YES)
  python scripts/run_e4b.py --stage execute --push      # E4B OpenJev run
  python scripts/run_e4b.py --stage e4c-protocol --push # freeze E4C construction protocol (no panel yet)
  python scripts/run_e4b.py --stage e4c-panel --push    # build + gate + freeze E4C panel (no model)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.run_experiment as rx  # noqa: E402
from experiments import e4b_ablation as mod  # noqa: E402

rx.EXPS["E4B"] = ("experiments.e4b_ablation", ["E4B_LATENCY_DECISION.md"])
_orig_dataset_atoms = rx.dataset_atoms


def _dataset_atoms_plus_runtime(dataset_id, group):
    atoms = _orig_dataset_atoms(dataset_id, group)
    if dataset_id == mod.IN_ID and group == "input_dataset":
        man = json.loads((ROOT / "evidence/openjev/RUNTIME_MANIFEST.json").read_text())
        if man.get("OPENJEV_LOADED") != "YES":
            raise SystemExit("E4B freeze requires OPENJEV_LOADED=YES (python scripts/openjev_runtime.py serve)")
        atoms += [rx.atom_record(x, "RuntimeIdentityFCO", "runtime") for x in mod.EXTRA_ATOMS]
        atoms += [rx.atom_record(x, "CodeFCO", "e4b_code") for x in mod.CODE]
    return atoms


def check_frozen():
    bp = rx.find_prereg(mod.EXP)
    if bp is None:
        raise SystemExit("no E4B prereg breakpoint")
    for a in bp["atoms"]:
        if a["group"] in ("runtime", "e4b_code") and hashlib.sha256((ROOT / a["path"]).read_bytes()).hexdigest() != a["sha256"]:
            raise SystemExit(f"frozen {a['group']} atom changed since {bp['breakpoint_id']}: {a['path']}")


def e4c(stage, push):
    from experiments import e4c_quality as q
    code = [rx.atom_record(x, "CodeFCO", "e4c_code") for x in q.CODE]
    doc = rx.atom_record("docs/prereg/E4C_QUALITY_CONSTRUCTION.md", "PreregistrationFCO", "prereg")
    if stage == "e4c-protocol":
        out = rx.create_breakpoint("e4c-quality-protocol", "PROTOCOL_FROZEN_PANEL_NOT_BUILT", [doc, *code],
                                   {"experiment_id": q.EXP, "stage": "E4C_PROTOCOL", "pre_mmr_root": rx.pre_mmr(),
                                    "note": "construction parameters frozen before any candidate state is generated"})
        paths = ["governance"]
    else:
        fz = None
        for f in sorted(rx.BP_DIR.glob("*.json")):
            d = json.loads(f.read_text())
            if d.get("stage") == "E4C_PROTOCOL":
                fz = d
        if fz is None:
            raise SystemExit("freeze the E4C protocol first (--stage e4c-protocol)")
        for x in fz["atoms"]:
            if hashlib.sha256((ROOT / x["path"]).read_bytes()).hexdigest() != x["sha256"]:
                raise SystemExit(f"E4C protocol atom changed since {fz['breakpoint_id']}: {x['path']}")
        man = q.build_input()
        atoms = rx.dataset_atoms(q.IN_ID, "input_dataset")
        state = "PANEL_FROZEN_GATE_PASS_NO_MODEL_CALLS" if man["gate"] == "PASS" else "BLOCKED_OR_UNDERPOWERED"
        out = rx.create_breakpoint("e4c-quality-panel", state, atoms,
                                   {"experiment_id": q.EXP, "stage": "E4C_PANEL", "protocol_breakpoint": fz["breakpoint_id"],
                                    "pre_mmr_root": rx.pre_mmr(), "gate": man["gate"], "input_dataset": {"dataset_id": q.IN_ID, "fmo_root": man["fmo_root"]}})
        paths = ["governance", "data/s01"]
    print(json.dumps({k: out[k] for k in ("bp_id", "bp_root", "mmr_size", "mmr_root_after")}, indent=2))
    if push:
        print("REMOTE_VERIFIED=" + rx.publish(f"e4c: {stage} ({out['bp_id']})", paths))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["prereg", "execute", "e4c-protocol", "e4c-panel"], required=True)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--branch", default="vithia-space")
    a = ap.parse_args()
    rx.BRANCH = a.branch
    rx.dataset_atoms = _dataset_atoms_plus_runtime
    if a.push:
        rx.preflight()
    if a.stage.startswith("e4c"):
        return e4c(a.stage, a.push)
    if a.stage == "prereg":
        rx.stage_prereg("E4B", a.push)
    else:
        check_frozen()
        rx.stage_execute("E4B", a.push)


if __name__ == "__main__":
    main()
