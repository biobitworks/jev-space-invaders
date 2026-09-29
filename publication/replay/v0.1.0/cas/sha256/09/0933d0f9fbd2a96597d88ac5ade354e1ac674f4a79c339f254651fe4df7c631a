#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "fcg" / "canonical"
REQUIRED = [
    "sources.jsonl","content_fcos.jsonl","occurrence_fcos.jsonl","context_fcos.jsonl",
    "transition_fcos.jsonl","fcg_edges.jsonl","claims.jsonl","evidence_bindings.jsonl",
    "experiments.jsonl","results.jsonl","datasets.jsonl","citations.jsonl",
    "breakpoints.jsonl","mmr_events.jsonl","artifact_registry.jsonl",
    "PUBLICATION_CLAIM_PATHS.jsonl",
]

def load(name):
    p = CANON / name
    assert p.exists(), f"missing {name}"
    rows=[]
    for n,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
        if line.strip():
            rows.append(json.loads(line))
    return rows

def main():
    data={name:load(name) for name in REQUIRED}
    claim_ids={x["claim_id"] for x in data["claims.jsonl"]}
    unresolved=[]
    for x in data["PUBLICATION_CLAIM_PATHS.jsonl"]:
        if x["claim_id"] not in claim_ids:
            unresolved.append(x["claim_id"])
    print(f"JSON_PARSE=PASS")
    print(f"CLAIM_PATH_AUDIT={'PASS' if not unresolved else 'FAIL'}")
    print(f"CLAIM_COUNT={len(data['claims.jsonl'])}")
    print(f"CONTENT_FCO_COUNT={len(data['content_fcos.jsonl'])}")
    print(f"OCCURRENCE_FCO_COUNT={len(data['occurrence_fcos.jsonl'])}")
    print(f"FCG_EDGE_COUNT={len(data['fcg_edges.jsonl'])}")
    print(f"EXPERIMENT_COUNT={len(data['experiments.jsonl'])}")
    print(f"BREAKPOINT_COUNT={len(data['breakpoints.jsonl'])}")
    if unresolved:
        print("UNRESOLVED=" + ",".join(unresolved))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
