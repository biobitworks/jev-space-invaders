#!/usr/bin/env python3
"""Derived views, regenerated from repository bytes (never hand-edited):
vita01/BREAKPOINT_REGISTRY.json, EXPERIMENT_REGISTRY.json, DATASET_REGISTRY.json, PUBLICATION_CLAIM_LEDGER.json."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vita01"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ledger = json.loads((ROOT / "governance/MMR_LEDGER.json").read_text()) if (ROOT / "governance/MMR_LEDGER.json").exists() else {"entries": []}
    in_ledger = {e["bp_file"]: e for e in ledger["entries"]}
    bps = []
    for f in sorted((ROOT / "governance/breakpoints").glob("*.json")):
        d = json.loads(f.read_text())
        rel = str(f.relative_to(ROOT))
        e = in_ledger.get(rel, {})
        bps.append({"breakpoint_id": d.get("breakpoint_id"), "parent": d.get("parent"), "state": d.get("state"),
                    "stage": d.get("stage"), "experiment_id": d.get("experiment_id"), "file": rel, "file_sha256": sha(f),
                    "root_kind": e.get("root_kind", "NOT_IN_LEDGER"), "bp_root": e.get("bp_root", "NOT_COMPUTED"),
                    "mmr_seq": e.get("seq"), "mmr_root_after": e.get("mmr_root_after", "NOT_COMPUTED"),
                    "signature_state": d.get("signature_state", "NOT_SIGNED"),
                    "verification_command": "python scripts/verify_breakpoints.py"})
    datasets = []
    for m in sorted((ROOT / "data/s01").glob("*/MANIFEST.json")):
        d = json.loads(m.read_text())
        datasets.append({k: d[k] for k in ("dataset_id", "kind", "source", "license", "fmo_root", "visibility",
                                           "claim_ceiling", "code_commit_at_generation")} |
                        {"manifest": str(m.relative_to(ROOT)), "manifest_sha256": sha(m), "evidence_level": "SIMULATED"})
    exps, claims = [], []
    for r in sorted((ROOT / "evidence/s01").glob("*/EXPERIMENT_RECEIPT.json")):
        d = json.loads(r.read_text())
        exps.append({"experiment_id": d["experiment_id"], "mode": d.get("mode", "EXPLORATORY_REHEARSAL"),
                     "terminal_state": d["terminal_state"], "input": d["input_dataset"]["dataset_id"],
                     "output": d["output_dataset"]["dataset_id"], "prereg_breakpoint": d.get("prereg_breakpoint"),
                     "code_freeze": d.get("code_freeze"), "replay_level": d.get("replay", {}).get("replay_level"),
                     "receipt": str(r.relative_to(ROOT)), "receipt_sha256": sha(r)})
        for c in d["claims"]:
            claims.append({"experiment_id": d["experiment_id"], "claim": c["id"], "state": c["state"],
                           "mode": d.get("mode", "EXPLORATORY_REHEARSAL"), "evidence_level": "SIMULATED",
                           "promotable_to_biological": False, "receipt": str(r.relative_to(ROOT))})
    OUT.mkdir(exist_ok=True)
    for name, rows in (("BREAKPOINT_REGISTRY", bps), ("DATASET_REGISTRY", datasets),
                       ("EXPERIMENT_REGISTRY", exps), ("PUBLICATION_CLAIM_LEDGER", claims)):
        (OUT / f"{name}.json").write_text(json.dumps({"generated_by": "scripts/build_registries.py",
                                                      "entries": rows}, indent=2) + "\n")
    print(f"breakpoints={len(bps)} datasets={len(datasets)} experiments={len(exps)} claims={len(claims)}")


if __name__ == "__main__":
    main()
