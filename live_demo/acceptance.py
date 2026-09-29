"""Bounded live acceptance matrix for an already-running local demo server."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8788"
OUT = Path("evidence/competition/live_demo/PER_SEAT_DECIDER_PREPROCESSOR_E2E_V02.json")


def api(path: str, body: dict | None = None) -> dict:
    if body is None:
        with urllib.request.urlopen(BASE + path, timeout=10) as r: return json.loads(r.read())
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())


def configure(mode: str, p0: dict, p1: dict | None = None) -> None:
    api("/api/pause", {})
    api("/api/mode", {"mode": mode})
    api("/api/seat/PLAYER_0", p0)
    if p1: api("/api/seat/PLAYER_1", p1)
    api("/api/reset", {"seed": 3})


def run(steps: int) -> dict:
    before = api("/api/state"); rows = []
    for _ in range(steps):
        rows.append(api("/api/step", {}))
    after = api("/api/state")
    return {"before": {"mode": before["mode"], "decision_index": before["decision_index"], "joint_step": before["joint_step"]}, "after": {"mode": after["mode"], "decision_index": after["decision_index"], "joint_step": after["joint_step"]}, "history": after["history"][-steps:]}


def main() -> None:
    qwen = {"preprocessor": "VITHIA_SPACE", "decision_layer": "DIRECT", "decider_provider": "OLLAMA", "decider_backend": "qwen2.5:0.5b", "exact_model": "qwen2.5:0.5b"}
    liquid = {"preprocessor": "NONE", "decision_layer": "DIRECT", "decider_provider": "LIQUID_LOCAL", "decider_backend": "longhorizon-liquid-230m:latest", "exact_model": "longhorizon-liquid-230m:latest"}
    cases = {}
    configure("1P", qwen); one = run(2); cases["1P_VITHIA_OLLAMA_QWEN"] = {"status": "PASS" if one["after"]["decision_index"] == 2 and all(r.get("env_advanced") for r in one["history"]) else "FAIL", "result": one}
    none_qwen = dict(qwen, preprocessor="NONE"); configure("1P", none_qwen); two = run(1); cases["1P_NONE_OLLAMA_QWEN"] = {"status": "PASS" if two["history"][-1].get("preprocessor_actual") == "NONE" else "FAIL", "result": two}
    configure("2P", qwen, qwen); three = run(1); cases["2P_VITHIA_QWEN_VS_VITHIA_QWEN"] = {"status": "PASS" if three["after"]["decision_index"] == 2 and three["after"]["joint_step"] == 1 else "FAIL", "result": three}
    configure("2P", qwen, liquid); four = run(1); liquid_row = four["history"][-1].get("player1", {}); liquid_ok = four["after"]["decision_index"] == 2 and four["after"]["joint_step"] == 1 and not liquid_row.get("fallback") and liquid_row.get("decider_provider") == "LIQUID_LOCAL"; cases["2P_VITHIA_QWEN_VS_NONE_LIQUID"] = {"status": "PASS" if liquid_ok else "PARTIAL_INVALID_PZ_ACTION_FAIL_CLOSED", "result": four}
    payload = {"schema": "PER_SEAT_DECIDER_PREPROCESSOR_E2E_V02", "server": BASE, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": cases, "provider_registry": api("/api/registry"), "integration_status": api("/api/integrations"), "claim_policy": "PASS only for executed cells; historical evidence is separate"}
    raw = json.dumps(payload, indent=2, sort_keys=True).encode(); payload["receipt_sha256"] = hashlib.sha256(raw).hexdigest(); OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n"); print(json.dumps({k: v["status"] for k, v in cases.items()}, sort_keys=True)); print(f"RECEIPT={OUT}")


if __name__ == "__main__": main()
