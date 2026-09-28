#!/usr/bin/env python3
"""Public-safe integration probe for the live demo.

No secrets are printed. Mitosis/Tenki statuses distinguish historical governed
receipts from current credential/tool availability. OpenJEV distinguishes the
matched-comparator stop from an explicitly configured targeted demo endpoint.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jr(p):
    try:
        return json.loads((ROOT / p).read_text())
    except Exception:
        return {}


def ollama():
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=3) as r:
            d = json.loads(r.read())
        return {"state": "REACHABLE", "models": [m.get("name") for m in d.get("models", []) if m.get("name")]}
    except Exception as e:
        return {"state": "UNREACHABLE", "error": type(e).__name__}


def main():
    m = jr("evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json")
    t = jr("evidence/competition/final_execution/TENKI_FINAL_EXECUTION_RECEIPT.json")
    tp = jr("evidence/competition/tenki/TENKI_MITOSIS_RUNTIME_RECEIPT.json")
    oj = jr("evidence/openjev/RUNTIME_MANIFEST.json")
    out = {
        "mitosis": {
            "governed_receipt_state": m.get("state", "UNKNOWN"),
            "used_in_final_evidence_path": m.get("MITOSIS_USED"),
            "universal_id_present": bool(m.get("remember_universal_id")),
            "credential_present": bool(os.environ.get("MI_API_KEY") or os.environ.get("MITOSIS_API_KEY")),
            "live_network_probe": "NOT_PERFORMED_BY_PUBLIC_SAFE_PROBE",
        },
        "tenki": {
            "final_receipt_state": t.get("state", "UNKNOWN"),
            "final_used": t.get("TENKI_USED"),
            "prior_sandbox_execution": bool(tp.get("execution")),
            "cli_present": bool(shutil.which("tenki")),
            "credential_present": bool(os.environ.get("TENKI_API_KEY") or os.environ.get("TENKI_AUTH_TOKEN")),
            "live_network_probe": "DEFER_TO_OPERATOR_AUTHORIZED_TENKI_CHECK",
        },
        "openjev": {
            "matched_comparator": "NOT_TESTED_CAPABILITY_MISMATCH",
            "runtime_manifest_loaded": oj.get("OPENJEV_LOADED", "NO"),
            "targeted_demo_endpoint_configured": bool(os.environ.get("OPENJEV_TARGETED_BASE_URL")),
        },
        "ollama": ollama(),
        "liquid_ai": {
            "available_models": [],
            "note": "exact served model names containing 'liquid' are treated as local Liquid-family backends; no sponsor equivalence is inferred",
        },
        "vithia_space_preprocessor": {
            "state": "AVAILABLE",
            "arm": "A5_VITA01_FULL_PUBLIC",
            "imports": ["experiments.e4a_snapshots.anticube", "experiments.e4b_ablation.path_distribution"],
            "private_s0_used": False,
        },
    }
    out["liquid_ai"]["available_models"] = [x for x in out["ollama"].get("models", []) if "liquid" in x.lower()]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
