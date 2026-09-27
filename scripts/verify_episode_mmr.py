#!/usr/bin/env python3
"""Recompute every run's per-decision leaves and episode MMR root from its trace file."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fmo import hp, mmr_root  # noqa: E402
from src.s01.canon import content_id  # noqa: E402

d = json.loads((ROOT / "results.json").read_text())
bad = 0
for r in d.get("runs", []) + d.get("baseline", {}).get("runs", []):
    if "episode_mmr_root" not in r:
        print(f"run {r.get('run')}: NO_EPISODE_MMR (predates per-decision leaves)")
        continue
    trace = [json.loads(l) for l in gzip.decompress((ROOT / r["trace_file"]).read_bytes()).splitlines()]
    leaves = []
    for rec in trace:
        body = {k: v for k, v in rec.items() if k not in ("leaf", "ms")}
        lf = hp("EPISODE_LEAF_V1", rec["t"], content_id(body))
        bad += lf.hex() != rec["leaf"]
        leaves.append(lf)
    root, _ = mmr_root(leaves)
    ok = root == r["episode_mmr_root"] and len(leaves) == r["episode_mmr_size"]
    bad += not ok
    print(f"run {r['run']} seed {r['seed']}: leaves={len(leaves)} root={root[:16]}… {'PASS' if ok else 'FAIL'}")
print("EPISODE_MMR_VERIFY=" + ("PASS" if not bad else "FAIL"))
sys.exit(1 if bad else 0)
