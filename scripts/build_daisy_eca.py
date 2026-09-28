#!/usr/bin/env python3
"""Build the model-free DAISY ECA corpora (D0-D3). No model calls. No breakpoints are created here:
sealing is a separate, explicit step once the corpus contract is frozen.

  python scripts/build_daisy_eca.py            # writes data/daisy/VITHIA_DAISY_ECA_{RULE,ACTION}_CORPUS_V1
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.daisy import eca_corpus as e  # noqa: E402
from src.s01.canon import write_jsonl, write_manifest  # noqa: E402

CODE = ["src/daisy/eca_corpus.py", "src/kernels/eca.py", "scripts/build_daisy_eca.py"]


def build(name, rows, schema, extra_cfg):
    d = ROOT / "data" / "daisy" / name
    d.mkdir(parents=True, exist_ok=True)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=name, schema=schema, kind="training_candidate", source="generated (deterministic, model-free)",
                          generation_code=CODE, config={"W": e.W, "ics": e.ICS, "ic_holdout": e.IC_HOLDOUT, **extra_cfg},
                          seeds={"ics": e.ICS}, license="CC-BY-4.0",
                          claim_ceiling="training-CANDIDATE corpus; no training contract frozen; not an E0-E4 evaluation dataset")


def main():
    rules = [e.rule_atom(r) for r in range(256)]
    trans = [row for r in range(256) for ic in e.ICS for row in e.transition_rows(r, ic)]
    acts = [row for r in range(256) for ic in e.ICS for row in e.action_rows(r, ic)]
    m1 = build("VITHIA_DAISY_ECA_RULE_CORPUS_V1", rules + trans, "D0 rule atoms + D1 transitions", {"T": e.T_TRAJ})
    m2 = build("VITHIA_DAISY_ECA_ACTION_CORPUS_V1", acts, "D2/D3 action rows (1P schema)",
               {"oracle_horizon": e.H_ORACLE, "a4_horizon": e.H_A4, "starts": e.STARTS, "actions": e.ACTIONS})
    print({"rule_corpus_root": m1["fmo_root"], "action_corpus_root": m2["fmo_root"],
           "rows": {"rule+transition": len(rules) + len(trans), "action": len(acts)}})


if __name__ == "__main__":
    main()
