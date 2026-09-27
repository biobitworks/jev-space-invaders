from __future__ import annotations
import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "results.json"
d = json.loads(p.read_text())
assert d.get("schema_version") == 2
assert isinstance(d.get("runs"), list)
all_runs = d["runs"] + d.get("baseline", {}).get("runs", [])
for r in all_runs:
    if "latency_ms_p50" in r and "latency_ms_p95" in r:
        assert r["latency_ms_p95"] >= r["latency_ms_p50"]
    if "model_calls" in r and "steps" in r:
        assert r["model_calls"] <= r["steps"]
    assert "score" in r
print("RESULTS_SCHEMA_CHECK=PASS")
print(f"JEV_RUNS={len(d['runs'])}")
print(f"BASELINE_RUNS={len(d.get('baseline', {}).get('runs', []))}")
