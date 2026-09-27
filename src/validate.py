"""Consistency checks judges apply (plus a few of ours). Raise on the first violation."""
from __future__ import annotations

import json
from pathlib import Path


def check(d: dict) -> dict:
    assert d.get("schema_version") == 2, "schema_version must be 2"
    runs = d.get("runs", [])
    base = d.get("baseline", {}).get("runs", [])
    assert isinstance(runs, list) and isinstance(base, list)
    for r in runs + base:
        tag = f"run {r.get('run', '?')} seed {r.get('seed', '?')}"
        assert "score" in r, f"{tag}: score missing"
        if "latency_ms_p50" in r and "latency_ms_p95" in r:
            assert r["latency_ms_p95"] >= r["latency_ms_p50"], f"{tag}: p95 < p50"
        if "model_calls" in r and "steps" in r:
            assert r["model_calls"] <= r["steps"], f"{tag}: model_calls > steps"
        if "frames" in r and "steps" in r and r["steps"]:
            assert r["frames"] >= r["steps"], f"{tag}: frames < steps"
        if r.get("provider") == "none":
            assert r.get("model_calls", 0) == 0, f"{tag}: no-model run has model_calls"
    counted = [r for r in runs if r.get("provider") == "typesafe"]
    return {"runs": len(runs), "counted_jev_runs": len(counted),
            "non_jev_runs": len(runs) - len(counted), "baseline_runs": len(base)}


def check_file(path: Path) -> dict:
    return check(json.loads(path.read_text()))
